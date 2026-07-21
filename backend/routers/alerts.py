from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Alert, Holding

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
def list_alerts(unread: bool = None, page: int = 1, size: int = 50, db: Session = Depends(get_db)):
    query = db.query(Alert)
    if unread:
        query = query.filter(Alert.read == False)
    total = query.count()
    alerts = query.order_by(Alert.created_at.desc()).offset((page - 1) * size).limit(size).all()
    items = []
    for a in alerts:
        h = db.query(Holding).filter(Holding.id == a.holding_id).first()
        items.append({
            "id": a.id,
            "holding_id": a.holding_id,
            "holding_name": h.name if h else "",
            "holding_code": h.code if h else "",
            "trigger_price": a.trigger_price,
            "current_price": a.current_price,
            "read": a.read,
            "created_at": a.created_at.isoformat() if a.created_at else "",
        })
    return {"items": items, "total": total}


@router.get("/count")
def alert_count(db: Session = Depends(get_db)):
    count = db.query(Alert).filter(Alert.read == False).count()
    return {"count": count}


@router.put("/{alert_id}/read")
def mark_read(alert_id: int, db: Session = Depends(get_db)):
    a = db.query(Alert).filter(Alert.id == alert_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="告警不存在")
    a.read = True
    db.commit()
    return {"ok": True}


@router.put("/read-all")
def mark_all_read(db: Session = Depends(get_db)):
    db.query(Alert).filter(Alert.read == False).update({"read": True})
    db.commit()
    return {"ok": True}
