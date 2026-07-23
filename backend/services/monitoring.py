from __future__ import annotations

import hashlib
import logging
import threading
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from config import config
from models import Alert, Holding, MonitoringCycle
from services.fixture_adapters import FixtureCalendar
from services.market_clock import local_now
from services.price_fetcher import fetch_all_prices, is_market_open
from services.provider_adapters import AkshareMarketCalendar
from services.quote_contracts import CalendarDecision, CalendarSource, MarketSession, ProviderErrorCode, QuoteState
from services.stop_loss import StopLossEngine, to_decimal
from services.shadow_projection import project_after_legacy_commit


logger = logging.getLogger(__name__)
_refresh_lock = threading.Lock()


class _DecisionCalendar:
    def __init__(self, decision: CalendarDecision):
        self.decision = decision

    def decide(self, _now=None) -> CalendarDecision:
        return self.decision


class MonitoringDatabaseBusy(RuntimeError):
    def __init__(self, cycle_id: str):
        super().__init__(ProviderErrorCode.DATABASE_BUSY.value)
        self.cycle_id = cycle_id
        self.error_code = ProviderErrorCode.DATABASE_BUSY.value


def _serialize_quote(result: dict) -> dict:
    return {
        **result,
        "current_price": float(result["current_price"]) if result.get("current_price") is not None else None,
        "quoted_at": result["quoted_at"].isoformat() if isinstance(result.get("quoted_at"), datetime) else result.get("quoted_at"),
        "fetched_at": result["fetched_at"].isoformat() if isinstance(result.get("fetched_at"), datetime) else result.get("fetched_at"),
        "fresh_until": result["fresh_until"].isoformat() if isinstance(result.get("fresh_until"), datetime) else result.get("fresh_until"),
    }


def _calendar_decision(now: datetime | None, price_loader, calendar) -> CalendarDecision:
    checked_at = local_now(now)
    if calendar is not None:
        return calendar.decide(checked_at)
    if price_loader is fetch_all_prices:
        adapter = FixtureCalendar() if config.fixture_price is not None else AkshareMarketCalendar()
        return adapter.decide(checked_at)
    market_open, degraded = is_market_open(now)
    return CalendarDecision(
        check_date=checked_at.date(), is_trading_day=market_open,
        session=MarketSession.OPEN if market_open else MarketSession.CLOSED,
        source=CalendarSource.WEEKDAY_FALLBACK if degraded else CalendarSource.AUTHORITATIVE,
        checked_at=checked_at, degraded_reason=ProviderErrorCode.CALENDAR_UNAVAILABLE.value if degraded else None,
    )


def _create_cycle(db: Session, *, cycle_id: str, kind: str, scope: str, started_at: datetime, calendar: CalendarDecision) -> MonitoringCycle:
    cycle = MonitoringCycle(
        id=cycle_id, kind=kind, scope=scope, status="failed",
        started_at=started_at.astimezone(timezone.utc).replace(tzinfo=None),
        calendar_source=calendar.source.value, degraded_reason=calendar.degraded_reason,
    )
    db.add(cycle)
    db.commit()
    return cycle


def _finish_cycle(
    db: Session, cycle: MonitoringCycle, *, status: str, requested: int = 0,
    succeeded: int = 0, skipped: int = 0, failed: int = 0, triggered: int = 0,
    error_code: str | None = None,
) -> None:
    cycle.status = status
    cycle.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
    cycle.requested_count = requested
    cycle.success_count = succeeded
    cycle.skipped_count = skipped
    cycle.failed_count = failed
    cycle.triggered_count = triggered
    cycle.coverage_pct = round(succeeded / requested * 100, 2) if requested else 100
    cycle.error_code = error_code
    db.commit()


def _response(db: Session, cycle: MonitoringCycle, decision: CalendarDecision, items: list[dict]) -> dict:
    alerts = db.query(Alert).filter(Alert.cycle_id == cycle.id).order_by(Alert.id).all()
    triggered = [{
        "id": alert.holding_id, "code": alert.holding_code, "name": alert.holding_name,
        "current_price": float(alert.current_price), "stop_loss_price": float(alert.trigger_price),
    } for alert in alerts]
    compatibility_status = "ok" if cycle.status == "success" else cycle.status
    return {
        "cycle_id": cycle.id, "status": compatibility_status, "market_open": decision.market_open,
        "calendar_degraded": decision.degraded, "requested": cycle.requested_count,
        "processed": cycle.success_count, "triggered": triggered,
        "items": [_serialize_quote(item) for item in items], "error_code": cycle.error_code,
    }


def _trigger_key(holding: Holding, sequence: int) -> str:
    rule = f"{holding.stop_loss_method}:{to_decimal(holding.stop_loss_value)}:{to_decimal(holding.stop_loss_price)}"
    identity = f"{holding.id}:{holding.created_at or 'new'}:{rule}:{sequence}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _legacy_quote_defaults(result: dict) -> dict:
    result = dict(result)
    if "state" not in result:
        result["state"] = "live" if result.get("fresh") and not result.get("error") else ("error" if result.get("error") else "stale")
    result.setdefault("fresh_until", result.get("fetched_at") if result.get("fresh") else None)
    result.setdefault("is_actionable", bool(result.get("fresh") and not result.get("error")))
    result.setdefault("error_code", "provider_unavailable" if result.get("error") else None)
    return result


def run_monitoring_cycle(
    db: Session, *, scheduled: bool = False, now: datetime | None = None,
    price_loader=fetch_all_prices, calendar=None, scope_code: str | None = None,
    scope_holding_id: int | None = None, lock_timeout: float | None = None,
) -> dict:
    cycle_id = uuid.uuid4().hex
    started_at = local_now(now)
    decision = _calendar_decision(now, price_loader, calendar)
    kind = "scheduled" if scheduled else ("scoped" if scope_code or scope_holding_id else "manual")
    scope = f"holding:{scope_holding_id}" if scope_holding_id else (f"code:{str(scope_code).zfill(6)}" if scope_code else "all")
    try:
        cycle = _create_cycle(db, cycle_id=cycle_id, kind=kind, scope=scope, started_at=started_at, calendar=decision)
    except OperationalError as exc:
        db.rollback()
        logger.warning("monitoring_database_busy", extra={"cycle_id": cycle_id, "outcome": ProviderErrorCode.DATABASE_BUSY.value, "error_class": type(exc).__name__})
        raise MonitoringDatabaseBusy(cycle_id) from exc

    timeout = 0 if scheduled else (config.refresh_lock_timeout_seconds if lock_timeout is None else lock_timeout)
    acquired = _refresh_lock.acquire(timeout=max(0, timeout))
    if not acquired:
        _finish_cycle(db, cycle, status="skipped", error_code=ProviderErrorCode.REFRESH_BUSY.value)
        return _response(db, cycle, decision, [])
    try:
        if scheduled and not decision.market_open:
            _finish_cycle(db, cycle, status="skipped", error_code="market_closed")
            return _response(db, cycle, decision, [])

        query = db.query(Holding).filter(Holding.status.in_(("holding", "triggered")))
        if scope_holding_id is not None:
            query = query.filter(Holding.id == scope_holding_id)
        if scope_code is not None:
            query = query.filter(Holding.code == str(scope_code).zfill(6))
        holdings = query.order_by(Holding.id).all()
        if not holdings:
            status = "degraded" if decision.degraded else "success"
            _finish_cycle(db, cycle, status=status)
            return _response(db, cycle, decision, [])

        by_key: dict[tuple[str, str], list[int]] = defaultdict(list)
        for holding in holdings:
            by_key[(holding.type, str(holding.code).zfill(6))].append(holding.id)
        if price_loader is fetch_all_prices:
            raw_results = price_loader(holdings, now=now, calendar=_DecisionCalendar(decision))
        else:
            raw_results = price_loader(holdings, now=now)
        quote_results = [_legacy_quote_defaults(item) for item in raw_results]
        received_keys = {(item["asset_type"], str(item["code"]).zfill(6)) for item in quote_results}
        for key in set(by_key) - received_keys:
            quote_results.append({
                "code": key[1], "asset_type": key[0], "current_price": None, "change_pct": None,
                "source": "none", "quoted_at": None, "fetched_at": started_at, "fresh_until": None,
                "fresh": False, "state": QuoteState.ERROR.value, "is_actionable": False,
                "error_code": ProviderErrorCode.NOT_FOUND.value, "error": "行情不可用",
            })

        succeeded = skipped = failed = 0
        for result in quote_results:
            key = (result["asset_type"], str(result["code"]).zfill(6))
            for holding_id in by_key.get(key, []):
                try:
                    with db.begin_nested():
                        holding = db.get(Holding, holding_id)
                        if holding is None:
                            skipped += 1
                            continue
                        state = str(result.get("state") or QuoteState.ERROR.value)
                        actionable = bool(result.get("is_actionable"))
                        holding.last_cycle_id = cycle_id
                        holding.is_actionable = actionable
                        holding.quote_state = state
                        holding.quote_error_code = result.get("error_code")
                        holding.fresh_until = result.get("fresh_until")
                        if not actionable or result.get("current_price") is None:
                            if state in {QuoteState.CLOSE.value, QuoteState.UNPRICED.value}:
                                skipped += 1
                            else:
                                failed += 1
                            continue

                        price = to_decimal(result["current_price"])
                        holding.current_price = price
                        holding.quote_source = result.get("source")
                        holding.quoted_at = result.get("quoted_at")
                        holding.fetched_at = result.get("fetched_at")
                        if price > to_decimal(holding.highest_price):
                            holding.highest_price = price
                        holding.stop_loss_price = StopLossEngine.calculate(
                            holding.buy_price, holding.highest_price, holding.stop_loss_method, holding.stop_loss_value,
                        )
                        if holding.status != "holding" or not StopLossEngine.is_triggered(price, holding.stop_loss_price):
                            succeeded += 1
                            continue
                        old_version = holding.version
                        sequence = holding.trigger_sequence + 1
                        idempotency_key = _trigger_key(holding, sequence)
                        db.flush()
                        won = db.query(Holding).filter(
                            Holding.id == holding.id, Holding.status == "holding", Holding.version == old_version,
                        ).update({
                            Holding.status: "triggered", Holding.version: old_version + 1,
                            Holding.trigger_sequence: sequence,
                        }, synchronize_session=False)
                        if won:
                            db.add(Alert(
                                holding_id=holding.id, holding_name=holding.name, holding_code=holding.code,
                                lifecycle_key=idempotency_key, idempotency_key=idempotency_key, cycle_id=cycle_id,
                                trigger_price=holding.stop_loss_price, current_price=price,
                                quote_source=holding.quote_source, quoted_at=holding.quoted_at,
                            ))
                            db.flush()
                        succeeded += 1
                except IntegrityError:
                    failed += 1
                    logger.info("trigger_idempotency_conflict", extra={"cycle_id": cycle_id, "outcome": "lost_race"})
                    db.expire_all()
                except Exception as exc:
                    failed += 1
                    logger.warning("instrument_failed", extra={
                        "cycle_id": cycle_id, "outcome": ProviderErrorCode.INSTRUMENT_FAILED.value,
                        "error_class": type(exc).__name__,
                    })

        try:
            db.commit()
            project_after_legacy_commit(db)
            # This follows the alert commit deliberately: delivery work is
            # optional and may fail independently without rolling back facts.
            from services.delivery import enqueue_committed_alerts
            enqueue_committed_alerts(db, db.query(Alert).filter(Alert.cycle_id == cycle_id).all())
        except OperationalError as exc:
            db.rollback()
            error_code = ProviderErrorCode.DATABASE_BUSY.value if "locked" in str(exc).lower() or "busy" in str(exc).lower() else "database_error"
            cycle = db.get(MonitoringCycle, cycle_id)
            if cycle is not None:
                _finish_cycle(db, cycle, status="failed", requested=len(holdings), failed=len(holdings), error_code=error_code)
                return _response(db, cycle, decision, quote_results)
            raise

        cycle = db.get(MonitoringCycle, cycle_id)
        assert cycle is not None
        if failed and succeeded:
            status = "partial"
        elif failed and not succeeded:
            status = "failed"
        elif decision.degraded:
            status = "degraded"
        else:
            status = "success"
        error_code = ProviderErrorCode.INSTRUMENT_FAILED.value if failed else decision.degraded_reason
        _finish_cycle(
            db, cycle, status=status, requested=len(holdings), succeeded=succeeded,
            skipped=skipped, failed=failed, triggered=db.query(Alert).filter(Alert.cycle_id == cycle_id).count(),
            error_code=error_code,
        )
        return _response(db, cycle, decision, quote_results)
    except Exception as exc:
        db.rollback()
        cycle = db.get(MonitoringCycle, cycle_id)
        if cycle is not None and cycle.finished_at is None:
            _finish_cycle(db, cycle, status="failed", error_code="cycle_failed")
        logger.exception("monitoring_cycle_failed", extra={"cycle_id": cycle_id, "error_class": type(exc).__name__})
        raise
    finally:
        _refresh_lock.release()
