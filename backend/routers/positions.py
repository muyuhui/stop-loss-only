from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Instrument, Position, PositionEvent, PositionQuote, StopRule
from schemas import ErrorResponse, PositionCloseRequest, PositionLotRequest, PositionOpenRequest, PositionRiskRequest, PositionRearmRequest
from services.supported_runtime import feature_not_supported


router = APIRouter(prefix="/positions", tags=["positions"])


def _decimal(value):
    return str(Decimal(str(value))) if value is not None else None


def _position(db: Session, position_id: int) -> Position:
    row = db.get(Position, position_id)
    if row is None:
        raise HTTPException(404, "position_not_found")
    return row


def _payload(db: Session, row: Position):
    item = db.get(Instrument, row.instrument_id)
    rule = db.query(StopRule).filter(StopRule.position_id == row.id, StopRule.is_active.is_(True)).first()
    return {
        "id": row.id, "code": item.code, "name": item.name, "asset_type": item.asset_type,
        "lifecycle_status": row.lifecycle_status, "risk_status": row.risk_status,
        "remaining_quantity": _decimal(row.remaining_quantity), "remaining_cost": _decimal(row.remaining_cost),
        "current_price": _decimal(row.current_price), "quote_state": row.quote_state,
        "is_actionable": row.is_actionable, "version": row.version, "trigger_sequence": row.trigger_sequence,
        "closed_at": row.closed_at, "active_stop_rule": None if rule is None else {
            "version": rule.version, "method": rule.method, "value": _decimal(rule.value),
            "stop_price": _decimal(rule.stop_price), "high_water_mark": _decimal(rule.high_water_mark),
        },
    }


def _writes_disabled():
    raise HTTPException(409, feature_not_supported("position_write"))


@router.get("")
def list_positions(
    lifecycle_status: str | None = Query(None, pattern="^(open|closed)$"),
    risk_status: str | None = Query(None, pattern="^(normal|triggered|acknowledged)$"),
    db: Session = Depends(get_db),
):
    query = db.query(Position)
    if lifecycle_status: query = query.filter(Position.lifecycle_status == lifecycle_status)
    if risk_status: query = query.filter(Position.risk_status == risk_status)
    return {"items": [_payload(db, p) for p in query.order_by(Position.id).all()]}


@router.post("", responses={409: {"model": ErrorResponse}})
def open_position(data: PositionOpenRequest, db: Session = Depends(get_db)):
    _writes_disabled()


@router.get("/{position_id}")
def get_position(position_id: int, db: Session = Depends(get_db)):
    return _payload(db, _position(db, position_id))


@router.get("/{position_id}/lots")
def lots(position_id: int, db: Session = Depends(get_db)):
    row = _position(db, position_id)
    return {"items": [{"id": lot.id, "quantity": _decimal(lot.quantity), "remaining_quantity": _decimal(lot.remaining_quantity), "unit_cost": _decimal(lot.unit_cost), "fees": _decimal(lot.fees), "taxes": _decimal(lot.taxes), "opened_at": lot.opened_at} for lot in row_lots(db, row)]}


def row_lots(db: Session, row: Position):
    from models import PositionLot
    return db.query(PositionLot).filter(PositionLot.position_id == row.id).order_by(PositionLot.opened_at, PositionLot.id).all()


@router.post("/{position_id}/lots", responses={409: {"model": ErrorResponse}})
def add_position_lot(position_id: int, data: PositionLotRequest, db: Session = Depends(get_db)):
    _writes_disabled()


@router.post("/{position_id}/close", responses={409: {"model": ErrorResponse}})
def close(position_id: int, data: PositionCloseRequest, db: Session = Depends(get_db)):
    _writes_disabled()


@router.post("/{position_id}/acknowledge", responses={409: {"model": ErrorResponse}})
def acknowledge(position_id: int, data: PositionRiskRequest, db: Session = Depends(get_db)):
    _writes_disabled()


@router.post("/{position_id}/rearm", responses={409: {"model": ErrorResponse}})
def rearm(position_id: int, data: PositionRearmRequest, db: Session = Depends(get_db)):
    _writes_disabled()


@router.get("/{position_id}/history")
def history(position_id: int, page: int = Query(1, ge=1), size: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    _position(db, position_id)
    events = db.query(PositionEvent).filter(PositionEvent.position_id == position_id).order_by(PositionEvent.occurred_at, PositionEvent.id).all()
    total = len(events)
    timeline = [{"id": e.id, "type": e.event_type, "occurred_at": e.occurred_at, "payload": e.payload, "schema_version": e.schema_version} for e in events[(page - 1) * size: page * size]]
    quotes = db.query(PositionQuote).filter(PositionQuote.position_id == position_id).order_by(PositionQuote.quoted_at, PositionQuote.id).all()
    # Ordinary quote points are uniformly sampled; event markers are never dropped.
    if len(quotes) > 1000:
        step = (len(quotes) - 1) / 999
        quotes = [quotes[round(index * step)] for index in range(1000)]
    return {"items": timeline, "total": total, "page": page, "size": size, "quotes": [{"price": _decimal(q.price), "quote_state": q.quote_state, "is_actionable": q.is_actionable, "quoted_at": q.quoted_at} for q in quotes]}
