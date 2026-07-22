from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Alert
from time_utils import as_market_time, as_utc


router = APIRouter(prefix="/alerts", tags=["alerts"])


def _payload(alert: Alert) -> dict:
    return {
        "id": alert.id, "holding_id": alert.holding_id, "holding_name": alert.holding_name,
        "holding_code": alert.holding_code, "trigger_price": float(alert.trigger_price),
        "current_price": float(alert.current_price), "quote_source": alert.quote_source,
        "quoted_at": as_market_time(alert.quoted_at).isoformat() if alert.quoted_at else None,
        "read": alert.read, "created_at": as_utc(alert.created_at).isoformat() if alert.created_at else None,
    }


@router.get("")
def list_alerts(unread: bool | None = None, page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    query = db.query(Alert)
    if unread is True:
        query = query.filter(Alert.read.is_(False))
    total = query.count()
    alerts = query.order_by(Alert.created_at.desc(), Alert.id.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": [_payload(item) for item in alerts], "total": total, "page": page, "size": size}


@router.get("/count")
def alert_count(db: Session = Depends(get_db)):
    return {"count": db.query(Alert).filter(Alert.read.is_(False)).count()}


@router.put("/read-all")
def mark_all_read(db: Session = Depends(get_db)):
    db.query(Alert).filter(Alert.read.is_(False)).update({"read": True})
    db.commit()
    return {"ok": True}


@router.put("/{alert_id}/read")
def mark_read(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    alert.read = True
    db.commit()
    return {"ok": True}
