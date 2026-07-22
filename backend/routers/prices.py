import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Holding
from services.monitoring import run_monitoring_cycle
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
    } for h in holdings]}


@router.post("/refresh", response_model=RefreshCycleResponse)
def refresh_prices(db: Session = Depends(get_db)):
    try:
        return run_monitoring_cycle(db, scheduled=False)
    except Exception as exc:
        correlation_id = uuid.uuid4().hex
        raise HTTPException(status_code=500, detail={"message": "价格刷新失败", "correlation_id": correlation_id}) from exc
