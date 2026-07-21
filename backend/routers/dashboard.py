from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config import config
from database import get_db
from models import Alert, Holding
from services.presentation import holding_payload
from services.stop_loss import to_decimal
from schemas import DashboardResponse


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db)):
    holdings = db.query(Holding).all()
    current = [h for h in holdings if h.status in ("holding", "triggered")]
    closed = [h for h in holdings if h.status == "closed"]
    active_cost = sum((to_decimal(h.buy_price) * h.quantity for h in current), start=to_decimal(0))
    active_value = sum((to_decimal(h.current_price) * h.quantity for h in current), start=to_decimal(0))
    unrealized = active_value - active_cost
    realized = sum(((to_decimal(h.close_price) - to_decimal(h.buy_price)) * h.quantity for h in closed if h.close_price is not None), start=to_decimal(0))
    unrealized_pct = round(float(unrealized / active_cost * 100), 2) if active_cost else 0.0

    tz = ZoneInfo(config.timezone)
    today = datetime.now(tz).date()
    # SQLite CURRENT_TIMESTAMP is stored as naive UTC; convert Shanghai day bounds
    # to the same representation before comparing.
    start = datetime.combine(today, time.min, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
    end = datetime.combine(today, time.max, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
    today_query = db.query(Alert).filter(Alert.created_at >= start, Alert.created_at <= end)
    latest = today_query.order_by(Alert.created_at.desc(), Alert.id.desc()).first()
    latest_payload = None
    if latest:
        latest_payload = {
            "id": latest.id, "holding_name": latest.holding_name, "holding_code": latest.holding_code,
            "trigger_price": float(latest.trigger_price), "current_price": float(latest.current_price),
            "created_at": latest.created_at,
        }
    counts = {name: sum(1 for h in holdings if h.status == name) for name in ("holding", "triggered", "closed")}
    return {
        "active_cost": float(active_cost), "active_market_value": float(active_value),
        "unrealized_profit_loss": float(unrealized), "unrealized_profit_loss_pct": unrealized_pct,
        "realized_profit_loss": float(realized), "holding_count": counts["holding"],
        "triggered_count": counts["triggered"], "closed_count": counts["closed"],
        "active_alerts_count": db.query(Alert).filter(Alert.read.is_(False)).count(),
        "today_alert_count": today_query.count(), "latest_alert": latest_payload,
        "holdings": [holding_payload(item) for item in current],
        # 兼容旧前端，后续完成迁移后可移除。
        "total_cost": float(active_cost), "total_market_value": float(active_value),
        "total_profit_loss": float(unrealized), "total_profit_loss_pct": unrealized_pct,
    }
