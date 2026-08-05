from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config import config
from database import get_db
from models import Alert, Holding, StopRuleHistory
from time_utils import as_utc
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

    # 本月账本：Asia/Shanghai 月界（1 日 00:00 至下月 1 日 00:00），与今日告警同口径转 naive UTC。
    now_shanghai = datetime.now(tz)
    month_start = datetime.combine(now_shanghai.date().replace(day=1), time.min, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
    next_month_start = datetime.combine((now_shanghai.date().replace(day=1) + timedelta(days=32)).replace(day=1), time.min, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)

    # 平仓时间归属：Holding 无 closed_at 列，closed 持仓不可再修改（更新被 400 拒绝），
    # 故 updated_at 在平仓后冻结，等价于平仓时间。
    month_closed = [h for h in closed if h.updated_at is not None and month_start <= h.updated_at < next_month_start]
    realized_month = sum(((to_decimal(h.close_price) - to_decimal(h.buy_price)) * h.quantity for h in month_closed), start=to_decimal(0))
    triggered_month = db.query(Alert).filter(Alert.created_at >= month_start, Alert.created_at < next_month_start).count()

    # 止损调整统计：月内全部历史行（含 create 基线）按持仓与时间排序；
    # 调整 = 来源 update/rearm；调低 = 调整后止损价低于该持仓上一条历史（月内或月前基线）。
    history_rows = (
        db.query(StopRuleHistory)
        .filter(StopRuleHistory.changed_at >= month_start, StopRuleHistory.changed_at < next_month_start)
        .order_by(StopRuleHistory.holding_id, StopRuleHistory.changed_at, StopRuleHistory.id)
        .all()
    )
    baseline_stop: dict[int, Decimal] = {}
    if history_rows:
        holding_ids = {row.holding_id for row in history_rows}
        for previous in (
            db.query(StopRuleHistory)
            .filter(StopRuleHistory.holding_id.in_(holding_ids), StopRuleHistory.changed_at < month_start)
            .order_by(StopRuleHistory.holding_id, StopRuleHistory.changed_at.desc(), StopRuleHistory.id.desc())
            .all()
        ):
            baseline_stop.setdefault(previous.holding_id, to_decimal(previous.stop_loss_price))
    adjustment_count = 0
    lowered_count = 0
    last_stop: dict[int, Decimal] = {}
    for row in history_rows:
        if row.holding_id not in last_stop:
            last_stop[row.holding_id] = baseline_stop.get(row.holding_id)
        if row.source in ("update", "rearm"):
            adjustment_count += 1
            if last_stop[row.holding_id] is not None and to_decimal(row.stop_loss_price) < last_stop[row.holding_id]:
                lowered_count += 1
        last_stop[row.holding_id] = to_decimal(row.stop_loss_price)

    # 最大浮亏来源：可估值当前持仓中浮亏金额最小（最负）者；无浮亏或无可估值持仓时为 null。
    largest_loss = None
    if priced:
        biggest_loss = min((((to_decimal(h.current_price) - to_decimal(h.buy_price)) * h.quantity, h) for h in priced), key=lambda pair: pair[0])
        if biggest_loss[0] < 0:
            largest_loss = {"name": biggest_loss[1].name, "code": biggest_loss[1].code, "profit_loss_amount": float(biggest_loss[0])}

    return {
        "active_cost": float(active_cost), "active_market_value": float(active_value),
        "unrealized_profit_loss": float(unrealized), "unrealized_profit_loss_pct": unrealized_pct,
        "realized_profit_loss": float(realized),
        "month_summary": {
            "month": now_shanghai.strftime("%Y-%m"),
            "realized_profit_loss": float(realized_month),
            "closed_count": len(month_closed),
            "triggered_count": triggered_month,
            "stop_adjustment_count": adjustment_count,
            "stop_lowered_count": lowered_count,
            "largest_loss": largest_loss,
        },
        "holding_count": counts["holding"],
        "triggered_count": counts["triggered"], "closed_count": counts["closed"],
        "active_alerts_count": db.query(Alert).filter(Alert.read.is_(False)).count(),
        "today_alert_count": today_query.count(), "latest_alert": latest_payload,
        "holdings": [holding_payload(item) for item in current],
        # 兼容旧前端，后续完成迁移后可移除。
        "total_cost": float(active_cost), "total_market_value": float(active_value),
        "total_profit_loss": float(unrealized), "total_profit_loss_pct": unrealized_pct,
    }
