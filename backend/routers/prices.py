import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Holding
from services.monitoring import MonitoringDatabaseBusy, run_monitoring_cycle
from schemas import RefreshCycleResponse
from time_utils import as_market_time


router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("")
def get_prices(db: Session = Depends(get_db)):
    holdings = db.query(Holding).filter(Holding.status.in_(("holding", "triggered"))).all()
    return {"items": [{
        "code": h.code, "name": h.name, "current_price": float(h.current_price),
        "source": h.quote_source,
        "quoted_at": as_market_time(h.quoted_at), "fetched_at": as_market_time(h.fetched_at),
        "state": h.quote_state, "fresh_until": as_market_time(h.fresh_until),
        "is_actionable": h.is_actionable, "error_code": h.quote_error_code,
    } for h in holdings]}


@router.post("/refresh", response_model=RefreshCycleResponse)
def refresh_prices(
    code: str | None = Query(None, min_length=1, max_length=20),
    holding_id: int | None = Query(None, ge=1), db: Session = Depends(get_db),
):
    try:
        if code is None and holding_id is None:
            result = run_monitoring_cycle(db, scheduled=False)
        else:
            result = run_monitoring_cycle(db, scheduled=False, scope_code=code, scope_holding_id=holding_id)
        if result.get("error_code") == "refresh_busy":
            raise HTTPException(status_code=409, detail={"message": "已有刷新正在运行", "error_code": "refresh_busy", "cycle_id": result["cycle_id"]})
        return result
    except MonitoringDatabaseBusy as exc:
        raise HTTPException(status_code=503, detail={"message": "数据库正忙", "error_code": exc.error_code, "cycle_id": exc.cycle_id}) from exc
    except Exception as exc:
        correlation_id = uuid.uuid4().hex
        raise HTTPException(status_code=500, detail={"message": "价格刷新失败", "correlation_id": correlation_id}) from exc


@router.post("/{code}/refresh", response_model=RefreshCycleResponse)
def refresh_instrument(code: str, db: Session = Depends(get_db)):
    return run_monitoring_cycle(db, scheduled=False, scope_code=code)
