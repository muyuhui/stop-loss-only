from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Holding, Alert
from services.stop_loss import StopLossEngine

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(db: Session = Depends(get_db)):
    holdings = db.query(Holding).all()
    total_cost = 0.0
    total_market_value = 0.0

    holding_items = []
    for h in holdings:
        sp = StopLossEngine.calculate(h.buy_price, h.highest_price, h.stop_loss_method, h.stop_loss_value)
        pnl = round((h.current_price - h.buy_price) / h.buy_price * 100, 2) if h.buy_price else 0
        dist = round((h.current_price - sp) / sp * 100, 2) if sp and sp > 0 else 0
        cost = h.buy_price * h.quantity
        mv = h.current_price * h.quantity if h.status == "holding" else (h.close_price or h.current_price) * h.quantity
        total_cost += cost
        total_market_value += mv
        holding_items.append({
            "id": h.id, "code": h.code, "name": h.name, "type": h.type,
            "buy_price": h.buy_price, "quantity": h.quantity, "buy_date": h.buy_date.isoformat() if h.buy_date else "",
            "current_price": h.current_price, "stop_loss_method": h.stop_loss_method,
            "stop_loss_value": h.stop_loss_value, "stop_loss_price": sp,
            "profit_loss_pct": pnl, "stop_loss_distance_pct": dist, "status": h.status,
        })

    total_pl = round(total_market_value - total_cost, 2)
    total_pl_pct = round(total_pl / total_cost * 100, 2) if total_cost > 0 else 0
    active_alerts = db.query(Alert).filter(Alert.read == False).count()

    return {
        "total_cost": round(total_cost, 2),
        "total_market_value": round(total_market_value, 2),
        "total_profit_loss": total_pl,
        "total_profit_loss_pct": total_pl_pct,
        "holding_count": len(holdings),
        "active_alerts_count": active_alerts,
        "holdings": holding_items,
    }
