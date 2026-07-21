from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import Alert, Holding
from services.price_fetcher import fetch_all_prices, is_market_open
from services.stop_loss import StopLossEngine, to_decimal


logger = logging.getLogger(__name__)


def _serialize_quote(result: dict) -> dict:
    return {
        **result,
        "current_price": float(result["current_price"]) if result.get("current_price") is not None else None,
        "quoted_at": result["quoted_at"].isoformat() if result.get("quoted_at") else None,
        "fetched_at": result["fetched_at"].isoformat() if result.get("fetched_at") else None,
    }


def run_monitoring_cycle(db: Session, *, scheduled: bool = False, now: datetime | None = None, price_loader=fetch_all_prices) -> dict:
    cycle_id = uuid.uuid4().hex
    market_open, degraded = is_market_open(now)
    if scheduled and not market_open:
        return {"cycle_id": cycle_id, "status": "skipped", "market_open": False, "calendar_degraded": degraded, "requested": 0, "processed": 0, "triggered": [], "items": []}

    holdings = db.query(Holding).filter(Holding.status.in_(("holding", "triggered"))).all()
    if not holdings:
        return {"cycle_id": cycle_id, "status": "ok", "market_open": market_open, "calendar_degraded": degraded, "requested": 0, "processed": 0, "triggered": [], "items": []}

    by_key: dict[tuple[str, str], list[Holding]] = defaultdict(list)
    for holding in holdings:
        by_key[(holding.type, str(holding.code).zfill(6))].append(holding)
    quote_results = price_loader(holdings, now=now)
    triggered = []
    processed = 0
    for result in quote_results:
        matches = by_key.get((result["asset_type"], str(result["code"]).zfill(6)), [])
        if result.get("error") or not result.get("fresh") or result.get("current_price") is None:
            continue
        for holding in matches:
            price = to_decimal(result["current_price"])
            holding.current_price = price
            holding.quote_source = result.get("source")
            holding.quoted_at = result.get("quoted_at")
            holding.fetched_at = result.get("fetched_at")
            if price > to_decimal(holding.highest_price):
                holding.highest_price = price
            holding.stop_loss_price = StopLossEngine.calculate(holding.buy_price, holding.highest_price, holding.stop_loss_method, holding.stop_loss_value)
            processed += 1
            if holding.status == "holding" and StopLossEngine.is_triggered(price, holding.stop_loss_price):
                holding.status = "triggered"
                lifecycle_key = f"holding-{holding.id}-{holding.created_at.isoformat() if holding.created_at else 'new'}"
                alert = Alert(
                    holding_id=holding.id, holding_name=holding.name, holding_code=holding.code,
                    lifecycle_key=lifecycle_key, trigger_price=holding.stop_loss_price,
                    current_price=price, quote_source=holding.quote_source, quoted_at=holding.quoted_at,
                )
                db.add(alert)
                triggered.append({"id": holding.id, "code": holding.code, "name": holding.name, "current_price": float(price), "stop_loss_price": float(holding.stop_loss_price)})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.info("监控周期 %s 命中告警幂等约束", cycle_id)
    status = "partial" if any(item.get("error") or not item.get("fresh") for item in quote_results) else "ok"
    return {
        "cycle_id": cycle_id, "status": status, "market_open": market_open,
        "calendar_degraded": degraded, "requested": len(holdings), "processed": processed,
        "triggered": triggered, "items": [_serialize_quote(item) for item in quote_results],
    }
