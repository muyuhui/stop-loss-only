from __future__ import annotations

from decimal import Decimal, ROUND_DOWN

from sqlalchemy.orm import Session

from models import Position, StopRule
from services.stop_loss import StopLossEngine


ZERO = Decimal("0")
HUNDRED = Decimal("100")
PERCENT_QUANTUM = Decimal("0.01")
FUND_QUANTUM = Decimal("0.000001")
STOCK_INCREMENT = Decimal("100")


def as_decimal(value) -> Decimal:
    return Decimal(str(value))


def decimal_string(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def percentage(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == 0:
        return None
    return (numerator / denominator * HUNDRED).quantize(PERCENT_QUANTUM)


def _active_rule(db: Session, position_id: int) -> StopRule | None:
    return (
        db.query(StopRule)
        .filter(StopRule.position_id == position_id, StopRule.is_active.is_(True))
        .order_by(StopRule.version.desc())
        .first()
    )


def risk_budget_summary(db: Session, settings: dict, *, estimated_exit_cost=ZERO) -> dict:
    positions = db.query(Position).filter(Position.lifecycle_status == "open").order_by(Position.id).all()
    total_cost = sum((as_decimal(row.remaining_cost) for row in positions), ZERO)
    covered_cost = ZERO
    used_risk = ZERO
    covered_count = 0
    uncovered_ids: list[int] = []

    for row in positions:
        quantity = as_decimal(row.remaining_quantity)
        cost = as_decimal(row.remaining_cost)
        rule = _active_rule(db, row.id)
        if quantity <= 0 or cost < 0 or rule is None or as_decimal(rule.stop_price) <= 0:
            uncovered_ids.append(row.id)
            continue
        covered_count += 1
        covered_cost += cost
        used_risk += max(ZERO, cost + estimated_exit_cost - as_decimal(rule.stop_price) * quantity)

    open_count = len(positions)
    coverage_complete = covered_count == open_count
    equity = settings.get("portfolio_equity")
    portfolio_pct = as_decimal(settings["portfolio_risk_limit_pct"])
    position_pct = as_decimal(settings["default_position_risk_limit_pct"])
    limit = as_decimal(equity) * portfolio_pct / HUNDRED if equity is not None else None
    utilization = percentage(used_risk, limit) if limit is not None else None
    exceeded = max(ZERO, used_risk - limit) if limit is not None else ZERO
    remaining = max(ZERO, limit - used_risk) if limit is not None and coverage_complete else None

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
            percentage(Decimal(covered_count), Decimal(open_count)) if open_count else None
        ),
        "total_open_remaining_cost": decimal_string(total_cost),
        "covered_remaining_cost": decimal_string(covered_cost),
        "cost_coverage_pct": decimal_string(percentage(covered_cost, total_cost)),
        "uncovered_position_ids": uncovered_ids,
    }


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
        "position_risk_limit_pct": decimal_string(as_decimal(data.position_risk_limit_pct)) if data.position_risk_limit_pct is not None else None,
    }


def _base_plan(data, budget: dict, increment: Decimal) -> dict:
    return {
        "status": "refused",
        "reason_code": None,
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
    }


def preview_position_plan(data, budget: dict) -> dict:
    increment = STOCK_INCREMENT if data.asset_type == "stock" else FUND_QUANTUM
    result = _base_plan(data, budget, increment)
    if budget["status"] == "unavailable":
        result["reason_code"] = "portfolio_equity_unset"
        return result
    if budget["status"] == "incomplete":
        result["reason_code"] = "portfolio_risk_coverage_incomplete"
        return result
    if budget["status"] in {"exhausted", "exceeded"}:
        result["reason_code"] = "portfolio_risk_capacity_exhausted"
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
    if data.asset_type == "stock":
        quantity = (raw // STOCK_INCREMENT) * STOCK_INCREMENT
    else:
        quantity = raw.quantize(FUND_QUANTUM, rounding=ROUND_DOWN)
    if quantity <= 0:
        result["reason_code"] = "quantity_below_minimum_increment"
        return result

    projected_loss = unit_risk * quantity + fees
    required_capital = entry * quantity + as_decimal(data.entry_fees)
    result.update({
        "status": "ready",
        "recommended_quantity": decimal_string(quantity),
        "projected_loss_at_stop": decimal_string(projected_loss),
        "required_capital": decimal_string(required_capital),
    })
    return result
