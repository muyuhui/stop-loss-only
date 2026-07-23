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


@router.get("/status", response_model=MonitoringStatusResponse)
def monitoring_status(db: Session = Depends(get_db)):
    latest = db.query(MonitoringCycle).order_by(MonitoringCycle.started_at.desc(), MonitoringCycle.id.desc()).first()
    success = db.query(MonitoringCycle).filter(
        MonitoringCycle.status.in_(("success", "degraded")), MonitoringCycle.success_count > 0,
    ).order_by(MonitoringCycle.finished_at.desc()).first()
    active = db.query(Holding).filter(Holding.status.in_(("holding", "triggered")))
    total = active.count()
    trusted = active.filter(Holding.is_actionable.is_(True)).count()
    coverage = round(trusted / total * 100, 2) if total else 100.0
    setting = db.query(Setting).filter(Setting.key == "monitor_interval").first()
    interval = int(setting.value) if setting else 5
    now = datetime.now(timezone.utc)
    last_success = as_utc(success.finished_at) if success else None
    overdue = last_success is None or now - last_success > timedelta(minutes=max(15, interval * 2))
    job = scheduler.get_job("price_monitor")
    next_run = getattr(job, "next_run_time", None) if job else None
    reason = "monitoring_overdue" if overdue and success else ("no_successful_cycle" if overdue else latest.degraded_reason if latest else None)
    return {
        "scheduler_running": scheduler.running, "next_run_at": next_run,
        "latest_cycle": _payload(latest), "last_success_at": last_success,
        "quote_coverage_pct": coverage, "overdue": overdue, "reason_code": reason,
    }


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
