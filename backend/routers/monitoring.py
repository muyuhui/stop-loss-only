from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Holding, MonitoringCycle, Setting
from scheduler import scheduler
from schemas import MonitoringCyclePage, MonitoringStatusResponse
from time_utils import as_utc


router = APIRouter(prefix="/monitoring", tags=["monitoring"])
VALUATION_STATES = ("live", "delayed", "close", "nav", "stale")


def _payload(cycle: MonitoringCycle | None) -> dict | None:
    if cycle is None:
        return None
    return {
        "id": cycle.id, "kind": cycle.kind, "scope": cycle.scope, "status": cycle.status,
        "started_at": as_utc(cycle.started_at), "finished_at": as_utc(cycle.finished_at),
        "requested_count": cycle.requested_count, "success_count": cycle.success_count,
        "skipped_count": cycle.skipped_count, "failed_count": cycle.failed_count,
        "triggered_count": cycle.triggered_count, "coverage_pct": float(cycle.coverage_pct),
        "calendar_source": cycle.calendar_source, "degraded_reason": cycle.degraded_reason,
        "error_code": cycle.error_code,
    }


def _coverage(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 2) if denominator else 100.0


def _status_payload(db: Session, *, now: datetime | None = None) -> dict:
    latest = db.query(MonitoringCycle).order_by(MonitoringCycle.started_at.desc(), MonitoringCycle.id.desc()).first()
    success = db.query(MonitoringCycle).filter(
        MonitoringCycle.status.in_(("success", "degraded")), MonitoringCycle.success_count > 0,
    ).order_by(MonitoringCycle.finished_at.desc()).first()
    active = db.query(Holding).filter(Holding.status.in_(("holding", "triggered")))
    total = active.count()
    actionable_count = active.filter(Holding.is_actionable.is_(True)).count()
    valuation_count = active.filter(
        Holding.current_price.isnot(None), Holding.quote_state.in_(VALUATION_STATES),
    ).count()
    actionable_coverage = _coverage(actionable_count, total)
    valuation_coverage = _coverage(valuation_count, total)
    setting = db.query(Setting).filter(Setting.key == "monitor_interval").first()
    interval = int(setting.value) if setting else 5
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    last_success = as_utc(success.finished_at) if success else None
    allowance = timedelta(minutes=max(15, interval * 2))
    latest_started = as_utc(latest.started_at) if latest else None
    authoritative_closed = bool(
        latest
        and latest.kind == "scheduled"
        and latest.status == "skipped"
        and latest.error_code == "market_closed"
        and latest.calendar_source == "authoritative"
        and latest_started
        and now - latest_started <= allowance
    )
    if authoritative_closed:
        freshness = "market_closed"
        overdue = False
        reason = "market_closed"
    elif last_success is None:
        freshness = "no_success"
        overdue = True
        reason = "no_successful_cycle"
    elif now - last_success > allowance:
        freshness = "overdue"
        overdue = True
        reason = "monitoring_overdue"
    else:
        freshness = "healthy"
        overdue = False
        reason = latest.degraded_reason if latest else None
    job = scheduler.get_job("price_monitor")
    next_run = getattr(job, "next_run_time", None) if job else None
    return {
        "scheduler_running": scheduler.running, "next_run_at": next_run,
        "latest_cycle": _payload(latest), "last_success_at": last_success,
        "freshness": freshness,
        "actionable_quote_coverage_pct": actionable_coverage,
        "valuation_quote_coverage_pct": valuation_coverage,
        "quote_coverage_pct": actionable_coverage,
        "overdue": overdue,
        "reason_code": reason,
    }


@router.get("/status", response_model=MonitoringStatusResponse)
def monitoring_status(db: Session = Depends(get_db)):
    return _status_payload(db)


@router.get("/cycles", response_model=MonitoringCyclePage)
def monitoring_cycles(
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status", pattern="^(success|partial|skipped|degraded|failed)$"),
    kind: str | None = Query(None, pattern="^(scheduled|manual|scoped)$"), db: Session = Depends(get_db),
):
    query = db.query(MonitoringCycle)
    if status_filter:
        query = query.filter(MonitoringCycle.status == status_filter)
    if kind:
        query = query.filter(MonitoringCycle.kind == kind)
    total = query.count()
    rows = query.order_by(MonitoringCycle.started_at.desc(), MonitoringCycle.id.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": [_payload(row) for row in rows], "total": total, "page": page, "size": size}
