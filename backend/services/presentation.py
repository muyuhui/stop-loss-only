from __future__ import annotations

from models import Holding
from services.stop_loss import StopLossEngine, to_decimal


def holding_payload(holding: Holding) -> dict:
    stop_loss_price = StopLossEngine.calculate(holding.buy_price, holding.highest_price, holding.stop_loss_method, holding.stop_loss_value)
    current = to_decimal(holding.current_price)
    buy = to_decimal(holding.buy_price)
    pnl = round(float((current - buy) / buy * 100), 2) if buy else 0.0
    distance = round(float((current - stop_loss_price) / current * 100), 2) if current > 0 else 0.0
    return {
        "id": holding.id, "code": holding.code, "name": holding.name, "type": holding.type,
        "buy_price": float(buy), "quantity": holding.quantity, "buy_date": holding.buy_date,
        "current_price": float(current), "highest_price": float(to_decimal(holding.highest_price)),
        "stop_loss_method": holding.stop_loss_method, "stop_loss_value": float(to_decimal(holding.stop_loss_value)),
        "stop_loss_price": float(stop_loss_price), "profit_loss_pct": pnl,
        "stop_loss_distance_pct": distance, "status": holding.status,
        "close_price": float(holding.close_price) if holding.close_price is not None else None,
        "quote_source": holding.quote_source, "quoted_at": holding.quoted_at, "fetched_at": holding.fetched_at,
        "created_at": holding.created_at, "updated_at": holding.updated_at,
    }
