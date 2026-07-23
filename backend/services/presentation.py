from __future__ import annotations

from models import CloseAllocation, Holding, Instrument, Position, StopRule
from services.stop_loss import StopLossEngine, to_decimal
from time_utils import as_market_time, as_utc


def holding_payload(holding: Holding) -> dict:
    stop_loss_price = StopLossEngine.calculate(holding.buy_price, holding.highest_price, holding.stop_loss_method, holding.stop_loss_value)
    quote_state = getattr(holding, "quote_state", None) or "unpriced"
    has_quote = quote_state != "unpriced" and holding.quoted_at is not None
    current = to_decimal(holding.current_price) if has_quote else None
    buy = to_decimal(holding.buy_price)
    pnl = round(float((current - buy) / buy * 100), 2) if current is not None and buy else 0.0
    distance = round(float((current - stop_loss_price) / current * 100), 2) if current is not None and current > 0 else 0.0
    return {
        "id": holding.id, "code": holding.code, "name": holding.name, "type": holding.type,
        "buy_price": float(buy), "quantity": holding.quantity, "buy_date": holding.buy_date,
        "current_price": float(current) if current is not None else None, "highest_price": float(to_decimal(holding.highest_price)),
        "stop_loss_method": holding.stop_loss_method, "stop_loss_value": float(to_decimal(holding.stop_loss_value)),
        "stop_loss_price": float(stop_loss_price), "profit_loss_pct": pnl,
        "stop_loss_distance_pct": distance, "status": holding.status,
        "close_price": float(holding.close_price) if holding.close_price is not None else None,
        "quote_source": holding.quote_source,
        "quoted_at": as_market_time(holding.quoted_at), "fetched_at": as_market_time(holding.fetched_at),
        "quote_state": quote_state, "fresh_until": as_market_time(getattr(holding, "fresh_until", None)),
        "is_actionable": bool(getattr(holding, "is_actionable", False)),
        "quote_error_code": getattr(holding, "quote_error_code", None),
        "last_cycle_id": getattr(holding, "last_cycle_id", None),
        "created_at": as_utc(holding.created_at), "updated_at": as_utc(holding.updated_at),
    }


def position_holding_payload(db, position: Position) -> dict:
    """Frozen legacy-holdings DTO sourced from the authoritative position model."""
    item = db.get(Instrument, position.instrument_id)
    rule = db.query(StopRule).filter(StopRule.position_id == position.id).order_by(StopRule.version.desc()).first()
    allocations = db.query(CloseAllocation).filter(CloseAllocation.position_id == position.id).all()
    close_price = allocations[-1].close_price if allocations else None
    status = "closed" if position.lifecycle_status == "closed" else ("triggered" if position.risk_status == "triggered" else "holding")
    quote = to_decimal(position.current_price) if position.current_price is not None else None
    cost = to_decimal(position.remaining_cost)
    quantity = to_decimal(position.remaining_quantity)
    unit_cost = cost / quantity if quantity else to_decimal(0)
    return {
        "id": position.id, "code": item.code, "name": item.name, "type": item.asset_type,
        "buy_price": float(unit_cost), "quantity": int(quantity) if item.asset_type == "stock" else float(quantity),
        "buy_date": position.created_at.date(), "current_price": float(quote) if quote is not None and position.lifecycle_status == "open" else None,
        "highest_price": float(rule.high_water_mark) if rule else float(unit_cost),
        "stop_loss_method": rule.method if rule else "fixed", "stop_loss_value": float(rule.value) if rule else 0.0001,
        "stop_loss_price": float(rule.stop_price) if rule else 0.0,
        "profit_loss_pct": round(float((quote - unit_cost) / unit_cost * 100), 2) if quote is not None and unit_cost else 0.0,
        "stop_loss_distance_pct": round(float((quote - rule.stop_price) / quote * 100), 2) if quote is not None and rule and quote else 0.0,
        "status": status, "close_price": float(close_price) if close_price is not None else None,
        "quote_source": "position-domain", "quoted_at": None, "fetched_at": None, "quote_state": position.quote_state,
        "fresh_until": None, "is_actionable": position.is_actionable, "quote_error_code": None,
        "last_cycle_id": None, "created_at": position.created_at, "updated_at": position.updated_at,
    }
