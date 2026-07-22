from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from models import Holding, PriceHistory
from services.market_clock import local_now
from services.price_fetcher import fetch_price_history
from services.stop_loss import StopLossEngine, to_decimal


RANGE_DAYS = {"1m": 30, "3m": 90, "6m": 180, "1y": 365}
STOP_LOSS_NOTE = "止损线按当前止损规则计算，不代表历史配置记录"


class HistoryUnavailable(RuntimeError):
    def __init__(self, message: str):
        super().__init__(message)
        self.correlation_id = uuid4().hex


def _cached(db: Session, holding: Holding, start: date, end: date) -> list[PriceHistory]:
    return (
        db.query(PriceHistory)
        .filter(
            PriceHistory.code == holding.code,
            PriceHistory.asset_type == holding.type,
            PriceHistory.trade_date >= start,
            PriceHistory.trade_date <= end,
        )
        .order_by(PriceHistory.trade_date.asc())
        .all()
    )


def _upsert(db: Session, holding: Holding, rows: list[dict], fetched_at) -> None:
    for row in rows:
        existing = db.query(PriceHistory).filter_by(
            code=holding.code, asset_type=holding.type, trade_date=row["trade_date"],
        ).first()
        if existing:
            existing.price = row["price"]
            existing.source = row["source"]
            existing.fetched_at = fetched_at
        else:
            db.add(PriceHistory(
                code=holding.code, asset_type=holding.type, trade_date=row["trade_date"],
                price=row["price"], source=row["source"], fetched_at=fetched_at,
            ))


def _points(holding: Holding, rows: list[PriceHistory]) -> list[dict]:
    running_high = to_decimal(holding.buy_price)
    result = []
    for row in rows:
        price = to_decimal(row.price)
        if price > running_high:
            running_high = price
        stop = StopLossEngine.calculate(
            holding.buy_price, running_high, holding.stop_loss_method, holding.stop_loss_value,
        )
        result.append({
            "trade_date": row.trade_date, "price": float(price),
            "stop_loss_price": float(stop), "triggered": StopLossEngine.is_triggered(price, stop),
        })
    return result


def holding_history(db: Session, holding: Holding, range_name: str) -> dict:
    today = local_now().date()
    start = max(holding.buy_date, today - timedelta(days=RANGE_DAYS[range_name]))
    cached = _cached(db, holding, start, today)
    fetched_today = bool(cached and cached[-1].fetched_at and cached[-1].fetched_at.date() == today)
    warning = None
    stale = False
    missing_ranges = []
    if not cached:
        missing_ranges.append((start, today))
    else:
        # A range can begin on a weekend or holiday; treat a first trading day
        # within one week as covered instead of repeatedly refetching it.
        if cached[0].trade_date > start + timedelta(days=7):
            missing_ranges.append((start, cached[0].trade_date - timedelta(days=1)))
        if not fetched_today and cached[-1].trade_date < today:
            missing_ranges.append((cached[-1].trade_date + timedelta(days=1), today))
    if missing_ranges:
        try:
            fetched_at = local_now()
            for fetch_start, fetch_end in missing_ranges:
                rows = fetch_price_history(holding.code, holding.type, fetch_start, fetch_end)
                _upsert(db, holding, rows, fetched_at)
            db.commit()
            cached = _cached(db, holding, start, today)
        except Exception as exc:
            db.rollback()
            if not cached:
                raise HistoryUnavailable(str(exc) or "历史行情暂时不可用") from exc
            stale = True
            warning = "历史行情更新失败，当前展示已有缓存"
    source = cached[-1].source if cached else None
    return {
        "holding_id": holding.id, "range": range_name, "buy_price": float(holding.buy_price),
        "stop_loss_method": holding.stop_loss_method, "stop_loss_note": STOP_LOSS_NOTE,
        "source": source, "last_trade_date": cached[-1].trade_date if cached else None,
        "stale": stale, "warning": warning, "points": _points(holding, cached),
    }
