from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN

from sqlalchemy.orm import Session

from models import Holding, MigrationAuthority, Position, StopRule
from services.stop_loss import StopLossEngine


ZERO = Decimal("0")
HUNDRED = Decimal("100")
PERCENT_QUANTUM = Decimal("0.01")
FUND_QUANTUM = Decimal("0.000001")
STOCK_INCREMENT = Decimal("100")


@dataclass(frozen=True)
class RiskExposure:
    record_id: int
    cost: Decimal
    risk: Decimal | None

    @property
    def covered(self) -> bool:
        return self.risk is not None


def as_decimal(value) -> Decimal:
    return Decimal(str(value))


def decimal_string(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def percentage(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == 0:
        return None
    return (numerator / denominator * HUNDRED).quantize(PERCENT_QUANTUM)


def read_authority_stage(db: Session) -> str:
    state = db.get(MigrationAuthority, 1)
    return state.stage if state is not None else "legacy"


def _active_rule(db: Session, position_id: int) -> StopRule | None:
    return (
        db.query(StopRule)
        .filter(StopRule.position_id == position_id, StopRule.is_active.is_(True))
        .order_by(StopRule.version.desc())
        .first()
    )


def _legacy_exposures(db: Session) -> list[RiskExposure]:
    rows = (
        db.query(Holding)
        .filter(Holding.status.in_(("holding", "triggered")))
        .order_by(Holding.id)
        .all()
    )
    exposures: list[RiskExposure] = []
    for row in rows:
        quantity = as_decimal(row.quantity)
        buy_price = as_decimal(row.buy_price)
        stop_price = as_decimal(row.stop_loss_price)
        cost = buy_price * quantity if quantity > 0 and buy_price > 0 else ZERO
        risk = None
        if quantity > 0 and buy_price > 0 and stop_price > 0:
            risk = max(ZERO, cost - stop_price * quantity)
        exposures.append(RiskExposure(record_id=row.id, cost=cost, risk=risk))
    return exposures


def _position_exposures(
    db: Session, *, estimated_exit_cost: Decimal = ZERO
) -> list[RiskExposure]:
    rows = (
        db.query(Position)
        .filter(Position.lifecycle_status == "open")
        .order_by(Position.id)
        .all()
    )
    exposures: list[RiskExposure] = []
    for row in rows:
        quantity = as_decimal(row.remaining_quantity)
        cost = as_decimal(row.remaining_cost)
        rule = _active_rule(db, row.id)
        risk = None
        if quantity > 0 and cost >= 0 and rule is not None and as_decimal(rule.stop_price) > 0:
            risk = max(
                ZERO,
                cost + estimated_exit_cost - as_decimal(rule.stop_price) * quantity,
            )
        exposures.append(
            RiskExposure(record_id=row.id, cost=max(ZERO, cost), risk=risk)
        )
    return exposures


def authoritative_risk_exposures(
    db: Session,
    authority_stage: str,
    *,
    estimated_exit_cost: Decimal = ZERO,
) -> list[RiskExposure]:
    if authority_stage in {"legacy", "shadow-read"}:
        return _legacy_exposures(db)
    return _position_exposures(db, estimated_exit_cost=estimated_exit_cost)


def risk_budget_summary(
    db: Session,
    settings: dict,
    *,
    authority_stage: str | None = None,
    estimated_exit_cost: Decimal = ZERO,
) -> dict:
    stage = authority_stage or read_authority_stage(db)
    exposures = authoritative_risk_exposures(
        db, stage, estimated_exit_cost=estimated_exit_cost
    )
    total_cost = sum((row.cost for row in exposures), ZERO)
    covered = [row for row in exposures if row.covered]
    covered_cost = sum((row.cost for row in covered), ZERO)
    used_risk = sum((row.risk for row in covered if row.risk is not None), ZERO)
    uncovered_ids = [row.record_id for row in exposures if not row.covered]

    open_count = len(exposures)
    covered_count = len(covered)
    coverage_complete = covered_count == open_count
    equity = settings.get("portfolio_equity")
    portfolio_pct = as_decimal(settings["portfolio_risk_limit_pct"])
    position_pct = as_decimal(settings["default_position_risk_limit_pct"])
    limit = as_decimal(equity) * portfolio_pct / HUNDRED if equity is not None else None
    utilization = percentage(used_risk, limit) if limit is not None else None
    exceeded = max(ZERO, used_risk - limit) if limit is not None else ZERO
    remaining = (
        max(ZERO, limit - used_risk)
        if limit is not None and coverage_complete
        else None
    )

    if equity is None:
        status, reason = "unavailable", "portfolio_equity_unset"
    elif not coverage_complete:
        status, reason = "incomplete", "portfolio_risk_coverage_incomplete"
    elif used_risk > limit:
        status, reason = "exceeded", "portfolio_risk_limit_exceeded"
    elif used_risk == limit:
        status, reason = "exhausted", "portfolio_risk_capacity_exhausted"
    else:
        status, reason = "available", None

    return {
        "status": status,
        "reason_code": reason,
        "portfolio_equity": decimal_string(as_decimal(equity)) if equity is not None else None,
        "portfolio_equity_updated_at": settings.get("portfolio_equity_updated_at"),
        "portfolio_risk_limit_pct": decimal_string(portfolio_pct),
        "default_position_risk_limit_pct": decimal_string(position_pct),
        "portfolio_limit_amount": decimal_string(limit),
        "used_risk_amount": decimal_string(used_risk),
        "remaining_capacity": decimal_string(remaining),
        "exceeded_amount": decimal_string(exceeded),
        "utilization_pct": decimal_string(utilization),
        "open_position_count": open_count,
        "covered_position_count": covered_count,
        "position_coverage_pct": decimal_string(
            percentage(Decimal(covered_count), Decimal(open_count))
            if open_count
            else None
        ),
        "total_open_remaining_cost": decimal_string(total_cost),
        "covered_remaining_cost": decimal_string(covered_cost),
        "cost_coverage_pct": decimal_string(percentage(covered_cost, total_cost)),
        "uncovered_position_ids": uncovered_ids,
    }


def _calculated_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalized_input(data) -> dict:
    return {
        "code": data.code.strip().zfill(6),
        "name": data.name.strip(),
        "asset_type": data.asset_type,
        "entry_price": decimal_string(as_decimal(data.entry_price)),
        "stop_method": data.stop_method,
        "stop_value": decimal_string(as_decimal(data.stop_value)),
        "entry_fees": decimal_string(as_decimal(data.entry_fees)),
        "estimated_exit_fees": decimal_string(as_decimal(data.estimated_exit_fees)),
        "position_risk_limit_pct": (
            decimal_string(as_decimal(data.position_risk_limit_pct))
            if data.position_risk_limit_pct is not None
            else None
        ),
    }


def _base_plan(data, budget: dict, increment: Decimal) -> dict:
    return {
        "plan_kind": "new",
        "status": "refused",
        "reason_code": None,
        "calculated_at": _calculated_at(),
        "normalized_input": _normalized_input(data),
        "budget": budget,
        "initial_stop_price": None,
        "effective_position_risk_limit_pct": None,
        "portfolio_limit_amount": budget["portfolio_limit_amount"],
        "position_limit_amount": None,
        "remaining_portfolio_capacity": budget["remaining_capacity"],
        "allowed_plan_risk": None,
        "entry_fees": decimal_string(as_decimal(data.entry_fees)),
        "estimated_exit_fees": decimal_string(as_decimal(data.estimated_exit_fees)),
        "unit_price_risk": None,
        "raw_quantity": None,
        "quantity_increment": decimal_string(increment),
        "recommended_quantity": None,
        "projected_loss_at_stop": None,
        "required_capital": None,
        "post_plan_portfolio_used_risk": None,
        "post_plan_portfolio_utilization_pct": None,
    }


def _budget_refusal_reason(budget: dict) -> str | None:
    if budget["status"] == "unavailable":
        return "portfolio_equity_unset"
    if budget["status"] == "incomplete":
        return "portfolio_risk_coverage_incomplete"
    if budget["status"] in {"exhausted", "exceeded"}:
        return "portfolio_risk_capacity_exhausted"
    return None


def preview_position_plan(data, budget: dict) -> dict:
    increment = STOCK_INCREMENT if data.asset_type == "stock" else FUND_QUANTUM
    result = _base_plan(data, budget, increment)
    if reason := _budget_refusal_reason(budget):
        result["reason_code"] = reason
        return result

    entry = as_decimal(data.entry_price)
    stop_value = as_decimal(data.stop_value)
    stop = StopLossEngine.calculate(entry, entry, data.stop_method, stop_value)
    result["initial_stop_price"] = decimal_string(stop)
    unit_risk = entry - stop
    result["unit_price_risk"] = decimal_string(unit_risk)
    if unit_risk <= 0:
        result["reason_code"] = "non_positive_unit_risk"
        return result
    valid, _ = StopLossEngine.validate(entry, data.stop_method, stop_value)
    if not valid:
        result["reason_code"] = "invalid_stop_rule"
        return result

    equity = as_decimal(budget["portfolio_equity"])
    portfolio_pct = as_decimal(budget["portfolio_risk_limit_pct"])
    effective_pct = (
        as_decimal(data.position_risk_limit_pct)
        if data.position_risk_limit_pct is not None
        else as_decimal(budget["default_position_risk_limit_pct"])
    )
    result["effective_position_risk_limit_pct"] = decimal_string(effective_pct)
    if effective_pct <= 0 or effective_pct > portfolio_pct:
        result["reason_code"] = "invalid_position_risk_limit"
        return result
    position_limit = equity * effective_pct / HUNDRED
    remaining = as_decimal(budget["remaining_capacity"])
    allowed = min(position_limit, remaining)
    result["position_limit_amount"] = decimal_string(position_limit)
    result["allowed_plan_risk"] = decimal_string(allowed)
    fees = as_decimal(data.entry_fees) + as_decimal(data.estimated_exit_fees)
    risk_for_quantity = allowed - fees
    if risk_for_quantity <= 0:
        result["reason_code"] = "fees_consume_risk_capacity"
        return result

    raw = risk_for_quantity / unit_risk
    result["raw_quantity"] = decimal_string(raw)
    quantity = _round_quantity(raw, data.asset_type)
    if quantity <= 0:
        result["reason_code"] = "quantity_below_minimum_increment"
        return result

    projected_loss = unit_risk * quantity + fees
    required_capital = entry * quantity + as_decimal(data.entry_fees)
    post_used = as_decimal(budget["used_risk_amount"]) + projected_loss
    portfolio_limit = as_decimal(budget["portfolio_limit_amount"])
    result.update(
        {
            "status": "ready",
            "recommended_quantity": decimal_string(quantity),
            "projected_loss_at_stop": decimal_string(projected_loss),
            "required_capital": decimal_string(required_capital),
            "post_plan_portfolio_used_risk": decimal_string(post_used),
            "post_plan_portfolio_utilization_pct": decimal_string(
                percentage(post_used, portfolio_limit)
            ),
        }
    )
    return result


def _round_quantity(raw: Decimal, asset_type: str) -> Decimal:
    if asset_type == "stock":
        return (raw // STOCK_INCREMENT) * STOCK_INCREMENT
    return raw.quantize(FUND_QUANTUM, rounding=ROUND_DOWN)


def _holding_snapshot(holding: Holding) -> dict:
    current_price = (
        None
        if holding.quote_state == "unpriced"
        else decimal_string(as_decimal(holding.current_price))
    )
    return {
        "id": holding.id,
        "version": holding.version,
        "code": holding.code,
        "name": holding.name,
        "asset_type": holding.type,
        "status": holding.status,
        "quantity": decimal_string(as_decimal(holding.quantity)),
        "buy_price": decimal_string(as_decimal(holding.buy_price)),
        "current_price": current_price,
        "quote_state": holding.quote_state,
        "is_actionable": bool(holding.is_actionable),
        "stop_loss_price": decimal_string(as_decimal(holding.stop_loss_price)),
    }


def _base_add_on_plan(data, budget: dict, holding: Holding) -> dict:
    asset_type = holding.type
    increment = STOCK_INCREMENT if asset_type == "stock" else FUND_QUANTUM
    return {
        "plan_kind": "add_on",
        "status": "refused",
        "reason_code": None,
        "calculated_at": _calculated_at(),
        "holding": _holding_snapshot(holding),
        "budget": budget,
        "planned_entry_price": decimal_string(as_decimal(data.planned_entry_price)),
        "existing_stop_price": decimal_string(as_decimal(holding.stop_loss_price)),
        "current_holding_risk": None,
        "effective_position_risk_limit_pct": None,
        "position_limit_amount": None,
        "remaining_position_capacity": None,
        "remaining_portfolio_capacity": budget["remaining_capacity"],
        "allowed_incremental_risk": None,
        "entry_fees": decimal_string(as_decimal(data.entry_fees)),
        "estimated_exit_fees": decimal_string(as_decimal(data.estimated_exit_fees)),
        "unit_price_risk": None,
        "raw_quantity": None,
        "quantity_increment": decimal_string(increment),
        "recommended_quantity": None,
        "incremental_projected_loss": None,
        "required_capital": None,
        "post_plan_holding_risk": None,
        "post_plan_portfolio_used_risk": None,
        "post_plan_portfolio_utilization_pct": None,
    }


def preview_add_on_plan(data, budget: dict, holding: Holding) -> dict:
    result = _base_add_on_plan(data, budget, holding)
    if holding.status != "holding":
        result["reason_code"] = "holding_not_eligible"
        return result

    quantity = as_decimal(holding.quantity)
    buy_price = as_decimal(holding.buy_price)
    stop_price = as_decimal(holding.stop_loss_price)
    if quantity <= 0 or buy_price <= 0 or stop_price <= 0:
        result["reason_code"] = "holding_risk_unavailable"
        return result
    current_risk = max(ZERO, (buy_price - stop_price) * quantity)
    result["current_holding_risk"] = decimal_string(current_risk)

    if reason := _budget_refusal_reason(budget):
        result["reason_code"] = reason
        return result

    planned_entry = as_decimal(data.planned_entry_price)
    unit_risk = planned_entry - stop_price
    result["unit_price_risk"] = decimal_string(unit_risk)
    if unit_risk <= 0:
        result["reason_code"] = "entry_not_above_existing_stop"
        return result

    equity = as_decimal(budget["portfolio_equity"])
    portfolio_pct = as_decimal(budget["portfolio_risk_limit_pct"])
    effective_pct = (
        as_decimal(data.position_risk_limit_pct)
        if data.position_risk_limit_pct is not None
        else as_decimal(budget["default_position_risk_limit_pct"])
    )
    result["effective_position_risk_limit_pct"] = decimal_string(effective_pct)
    if effective_pct <= 0 or effective_pct > portfolio_pct:
        result["reason_code"] = "invalid_position_risk_limit"
        return result
    position_limit = equity * effective_pct / HUNDRED
    remaining_position = max(ZERO, position_limit - current_risk)
    remaining_portfolio = as_decimal(budget["remaining_capacity"])
    allowed = min(remaining_position, remaining_portfolio)
    result.update(
        {
            "position_limit_amount": decimal_string(position_limit),
            "remaining_position_capacity": decimal_string(remaining_position),
            "allowed_incremental_risk": decimal_string(allowed),
        }
    )
    if remaining_position <= 0:
        result["reason_code"] = "position_risk_capacity_exhausted"
        return result
    if remaining_portfolio <= 0:
        result["reason_code"] = "portfolio_risk_capacity_exhausted"
        return result

    fees = as_decimal(data.entry_fees) + as_decimal(data.estimated_exit_fees)
    risk_for_quantity = allowed - fees
    if risk_for_quantity <= 0:
        result["reason_code"] = "fees_consume_risk_capacity"
        return result
    raw = risk_for_quantity / unit_risk
    result["raw_quantity"] = decimal_string(raw)
    add_quantity = _round_quantity(raw, holding.type)
    if add_quantity <= 0:
        result["reason_code"] = "quantity_below_minimum_increment"
        return result

    incremental_loss = unit_risk * add_quantity + fees
    required_capital = planned_entry * add_quantity + as_decimal(data.entry_fees)
    post_holding = current_risk + incremental_loss
    post_portfolio = as_decimal(budget["used_risk_amount"]) + incremental_loss
    portfolio_limit = as_decimal(budget["portfolio_limit_amount"])
    result.update(
        {
            "status": "ready",
            "recommended_quantity": decimal_string(add_quantity),
            "incremental_projected_loss": decimal_string(incremental_loss),
            "required_capital": decimal_string(required_capital),
            "post_plan_holding_risk": decimal_string(post_holding),
            "post_plan_portfolio_used_risk": decimal_string(post_portfolio),
            "post_plan_portfolio_utilization_pct": decimal_string(
                percentage(post_portfolio, portfolio_limit)
            ),
        }
    )
    return result
