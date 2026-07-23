from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum

from sqlalchemy.orm import Session

from models import Account, CloseAllocation, Instrument, Position, PositionEvent, PositionLot, StopRule, PRICE_SCALE, QUANTITY_SCALE
from services.stop_loss import StopLossEngine


PRICE_QUANTUM = Decimal("1").scaleb(-PRICE_SCALE)
QUANTITY_QUANTUM = Decimal("1").scaleb(-QUANTITY_SCALE)


class LifecycleStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class RiskStatus(StrEnum):
    NORMAL = "normal"
    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"


def decimal_price(value) -> Decimal:
    value = Decimal(str(value)).quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP)
    if value <= 0:
        raise ValueError("price_must_be_positive")
    return value


def decimal_quantity(value, asset_type: str) -> Decimal:
    quantity = Decimal(str(value)).quantize(QUANTITY_QUANTUM, rounding=ROUND_HALF_UP)
    if quantity <= 0:
        raise ValueError("quantity_must_be_positive")
    if asset_type == "stock" and quantity != quantity.to_integral_value():
        raise ValueError("stock_quantity_must_be_integral")
    return quantity


def utc_now(clock=None) -> datetime:
    return (clock() if clock else datetime.now(timezone.utc)).astimezone(timezone.utc)


def event(db: Session, position: Position, event_type: str, payload: dict, *, clock=None) -> PositionEvent:
    row = PositionEvent(position_id=position.id, event_type=event_type, payload=json.dumps(payload, ensure_ascii=False, sort_keys=True), occurred_at=utc_now(clock))
    db.add(row)
    return row


def default_account(db: Session) -> Account:
    account = db.query(Account).filter(Account.is_default.is_(True)).first()
    if account is None:
        account = Account(name="本地默认账户", cost_basis_method="fifo", is_default=True)
        db.add(account)
        db.flush()
    return account


def instrument(db: Session, *, code: str, asset_type: str, name: str) -> Instrument:
    normalized = str(code).strip().zfill(6)
    row = db.query(Instrument).filter(Instrument.asset_type == asset_type, Instrument.code == normalized).first()
    if row is None:
        row = Instrument(asset_type=asset_type, code=normalized, name=name.strip())
        db.add(row)
        db.flush()
    elif name and row.name != name.strip():
        row.name = name.strip()
    return row


def add_lot(db: Session, position: Position, *, quantity, unit_cost, fees=0, taxes=0, opened_at=None, clock=None) -> PositionLot:
    if position.lifecycle_status != LifecycleStatus.OPEN:
        raise ValueError("position_closed")
    asset_type = db.get(Instrument, position.instrument_id).asset_type
    quantity = decimal_quantity(quantity, asset_type)
    unit_cost, fees, taxes = decimal_price(unit_cost), Decimal(str(fees)), Decimal(str(taxes))
    row = PositionLot(position_id=position.id, quantity=quantity, remaining_quantity=quantity, unit_cost=unit_cost, fees=fees, taxes=taxes, opened_at=opened_at or utc_now(clock))
    db.add(row)
    position.remaining_quantity = Decimal(str(position.remaining_quantity)) + quantity
    position.remaining_cost = Decimal(str(position.remaining_cost)) + quantity * unit_cost + fees + taxes
    position.version += 1
    event(db, position, "lot_added", {"quantity": str(quantity), "unit_cost": str(unit_cost)}, clock=clock)
    return row


def create_position(db: Session, *, code: str, asset_type: str, name: str, quantity, unit_cost, fees=0, taxes=0, opened_at=None, clock=None) -> Position:
    account = default_account(db)
    item = instrument(db, code=code, asset_type=asset_type, name=name)
    position = Position(account_id=account.id, instrument_id=item.id, remaining_quantity=0, remaining_cost=0)
    db.add(position)
    db.flush()
    add_lot(db, position, quantity=quantity, unit_cost=unit_cost, fees=fees, taxes=taxes, opened_at=opened_at, clock=clock)
    event(db, position, "position_opened", {"instrument_id": item.id}, clock=clock)
    return position


def close_position(db: Session, position: Position, *, quantity, close_price, fees=0, taxes=0, closed_at=None, clock=None) -> list[CloseAllocation]:
    if position.lifecycle_status != LifecycleStatus.OPEN:
        raise ValueError("position_closed")
    asset_type = db.get(Instrument, position.instrument_id).asset_type
    quantity, close_price = decimal_quantity(quantity, asset_type), decimal_price(close_price)
    remaining = Decimal(str(position.remaining_quantity))
    if quantity > remaining:
        raise ValueError("close_quantity_exceeds_remaining")
    fees, taxes, remaining_to_allocate = Decimal(str(fees)), Decimal(str(taxes)), quantity
    when = closed_at or utc_now(clock)
    allocations = []
    lots = db.query(PositionLot).filter(PositionLot.position_id == position.id, PositionLot.remaining_quantity > 0).order_by(PositionLot.opened_at, PositionLot.id).all()
    for lot in lots:
        if remaining_to_allocate <= 0:
            break
        lot_remaining = Decimal(str(lot.remaining_quantity))
        allocated = min(remaining_to_allocate, lot_remaining)
        ratio = allocated / quantity
        allocation_fees, allocation_taxes = fees * ratio, taxes * ratio
        cost = allocated * Decimal(str(lot.unit_cost)) + Decimal(str(lot.fees)) * (allocated / Decimal(str(lot.quantity))) + Decimal(str(lot.taxes)) * (allocated / Decimal(str(lot.quantity)))
        proceeds = allocated * close_price - allocation_fees - allocation_taxes
        row = CloseAllocation(position_id=position.id, lot_id=lot.id, quantity=allocated, unit_cost=Decimal(str(lot.unit_cost)), close_price=close_price, fees=allocation_fees, taxes=allocation_taxes, proceeds=proceeds, realized_pnl=proceeds - cost, closed_at=when)
        db.add(row); allocations.append(row)
        lot.remaining_quantity = lot_remaining - allocated
        remaining_to_allocate -= allocated
    position.remaining_quantity = remaining - quantity
    position.remaining_cost = sum((Decimal(str(l.remaining_quantity)) * Decimal(str(l.unit_cost)) + Decimal(str(l.fees)) * (Decimal(str(l.remaining_quantity)) / Decimal(str(l.quantity))) + Decimal(str(l.taxes)) * (Decimal(str(l.remaining_quantity)) / Decimal(str(l.quantity))) for l in lots), Decimal("0"))
    if position.remaining_quantity == 0:
        position.lifecycle_status, position.closed_at = LifecycleStatus.CLOSED, when
    position.version += 1
    event(db, position, "position_closed" if position.lifecycle_status == LifecycleStatus.CLOSED else "position_partially_closed", {"quantity": str(quantity), "close_price": str(close_price)}, clock=clock)
    return allocations


def activate_rule(db: Session, position: Position, *, method: str, value, reason: str | None = None, clock=None) -> StopRule:
    value = decimal_price(value)
    old = db.query(StopRule).filter(StopRule.position_id == position.id, StopRule.is_active.is_(True)).first()
    if old:
        old.is_active, old.deactivated_at = False, utc_now(clock)
    high = Decimal(str(position.current_price or 0)) or (Decimal(str(position.remaining_cost)) / Decimal(str(position.remaining_quantity)))
    stop = StopLossEngine.calculate(high, high, method, value)
    version = (old.version if old else 0) + 1
    rule = StopRule(position_id=position.id, version=version, method=method, value=value, stop_price=stop, high_water_mark=high, activated_at=utc_now(clock))
    db.add(rule); position.version += 1
    event(db, position, "rule_activated", {"rule_version": version, "reason": reason}, clock=clock)
    return rule


def acknowledge_risk(db: Session, position: Position, *, expected_version: int, reason: str, clock=None) -> None:
    if not reason.strip() or position.risk_status != RiskStatus.TRIGGERED or position.version != expected_version:
        raise ValueError("risk_acknowledgement_rejected")
    position.risk_status, position.version = RiskStatus.ACKNOWLEDGED, position.version + 1
    event(db, position, "risk_acknowledged", {"reason": reason.strip()}, clock=clock)


def rearm_position(db: Session, position: Position, *, expected_version: int, method: str, value, reason: str, clock=None) -> StopRule:
    if not reason.strip() or position.lifecycle_status != LifecycleStatus.OPEN or position.risk_status not in {RiskStatus.TRIGGERED, RiskStatus.ACKNOWLEDGED} or position.version != expected_version:
        raise ValueError("position_rearm_rejected")
    rule = activate_rule(db, position, method=method, value=value, reason=reason.strip(), clock=clock)
    if position.is_actionable and position.current_price is not None and Decimal(str(position.current_price)) <= Decimal(str(rule.stop_price)):
        raise ValueError("new_rule_already_breached")
    position.risk_status, position.trigger_sequence, position.version = RiskStatus.NORMAL, position.trigger_sequence + 1, position.version + 1
    event(db, position, "position_rearmed", {"reason": reason.strip(), "trigger_sequence": position.trigger_sequence}, clock=clock)
    return rule


def position_stop_metrics(position: Position, rule: StopRule | None, *, estimated_exit_cost=Decimal("0")) -> dict:
    quantity, cost = Decimal(str(position.remaining_quantity)), Decimal(str(position.remaining_cost))
    if not rule or not quantity or position.current_price is None:
        return {"remaining_unit_cost": None, "stop_risk_amount": None, "pnl_at_stop": None, "estimated_loss_at_stop": None, "estimated_exit_cost": estimated_exit_cost, "exit_cost_basis": "gross" if estimated_exit_cost == 0 else "configured"}
    unit_cost, current, stop = cost / quantity, Decimal(str(position.current_price)), Decimal(str(rule.stop_price))
    pnl_at_stop = (stop - unit_cost) * quantity - estimated_exit_cost
    return {"remaining_unit_cost": unit_cost, "stop_risk_amount": max(Decimal("0"), current - stop) * quantity, "pnl_at_stop": pnl_at_stop, "estimated_loss_at_stop": max(Decimal("0"), -pnl_at_stop), "estimated_exit_cost": estimated_exit_cost, "exit_cost_basis": "gross" if estimated_exit_cost == 0 else "configured"}


def portfolio_metrics(positions: list[Position], *, exit_cost=Decimal("0")) -> dict:
    open_positions = [p for p in positions if p.lifecycle_status == LifecycleStatus.OPEN]
    actionable = [p for p in open_positions if p.is_actionable and p.current_price is not None]
    total_cost = sum((Decimal(str(p.remaining_cost)) for p in open_positions), Decimal("0"))
    covered_cost = sum((Decimal(str(p.remaining_cost)) for p in actionable), Decimal("0"))
    market_total = sum((Decimal(str(p.current_price)) * Decimal(str(p.remaining_quantity)) for p in actionable), Decimal("0"))
    return {"open_position_count": len(open_positions), "actionable_open_position_count": len(actionable), "actionable_position_coverage_pct": (Decimal(len(actionable)) / Decimal(len(open_positions)) * 100 if open_positions else None), "total_open_remaining_cost": total_cost, "covered_remaining_cost": covered_cost, "valuation_coverage_pct": (covered_cost / total_cost * 100 if total_cost else None), "total_actionable_market_value": market_total, "exit_cost_basis": "gross" if exit_cost == 0 else "configured"}
