from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config import config
from database import get_db
from models import Alert, CloseAllocation, Holding, Position
from time_utils import as_utc
from services.presentation import holding_payload, position_holding_payload
from services.position_domain import portfolio_metrics
from services.shadow_projection import authority
from services.stop_loss import to_decimal
from schemas import DashboardResponse


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db)):
    if authority(db).stage == "new-authoritative":
        positions = db.query(Position).all()
        stats = portfolio_metrics(positions)
        open_rows = [row for row in positions if row.lifecycle_status == "open"]
        allocations = db.query(CloseAllocation).all()
        realized = sum((to_decimal(row.realized_pnl) for row in allocations), start=to_decimal(0))
        value = stats["total_actionable_market_value"]
        cost = stats["covered_remaining_cost"]
        unrealized = value - cost
        counts = {"holding": sum(row.risk_status == "normal" for row in open_rows), "triggered": sum(row.risk_status == "triggered" for row in open_rows), "closed": sum(row.lifecycle_status == "closed" for row in positions)}
        return {
            "active_cost": float(stats["total_open_remaining_cost"]), "active_market_value": float(value),
            "unrealized_profit_loss": float(unrealized), "unrealized_profit_loss_pct": round(float(unrealized / cost * 100), 2) if cost else 0.0,
            "realized_profit_loss": float(realized), "holding_count": counts["holding"], "triggered_count": counts["triggered"], "closed_count": counts["closed"],
            "active_alerts_count": db.query(Alert).filter(Alert.read.is_(False)).count(), "today_alert_count": 0, "latest_alert": None,
            "holdings": [position_holding_payload(db, row) for row in open_rows],
            "total_cost": float(stats["total_open_remaining_cost"]), "total_market_value": float(value), "total_profit_loss": float(unrealized), "total_profit_loss_pct": round(float(unrealized / cost * 100), 2) if cost else 0.0,
            "actionable_position_coverage_pct": float(stats["actionable_position_coverage_pct"]) if stats["actionable_position_coverage_pct"] is not None else None,
            "valuation_coverage_pct": float(stats["valuation_coverage_pct"]) if stats["valuation_coverage_pct"] is not None else None,
        }
    holdings = db.query(Holding).all()
    current = [h for h in holdings if h.status in ("holding", "triggered")]
    closed = [h for h in holdings if h.status == "closed"]
    active_cost = sum((to_decimal(h.buy_price) * h.quantity for h in current), start=to_decimal(0))
    priced = [h for h in current if h.quote_state != "unpriced" and h.current_price is not None]
    active_value = sum((to_decimal(h.current_price) * h.quantity for h in priced), start=to_decimal(0))
    valuation_cost = sum((to_decimal(h.buy_price) * h.quantity for h in priced), start=to_decimal(0))
    unrealized = active_value - valuation_cost
    realized = sum(((to_decimal(h.close_price) - to_decimal(h.buy_price)) * h.quantity for h in closed if h.close_price is not None), start=to_decimal(0))
    unrealized_pct = round(float(unrealized / valuation_cost * 100), 2) if valuation_cost else 0.0

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
            "created_at": as_utc(latest.created_at),
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
