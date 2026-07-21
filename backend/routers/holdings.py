from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Holding
from schemas import HoldingCreate, HoldingUpdate, HoldingClose, HoldingResponse, HoldingListResponse
from services.stop_loss import StopLossEngine

router = APIRouter(prefix="/holdings", tags=["holdings"])


def _compute_fields(h: Holding):
    stop_loss_price = StopLossEngine.calculate(h.buy_price, h.highest_price, h.stop_loss_method, h.stop_loss_value)
    profit_loss_pct = round((h.current_price - h.buy_price) / h.buy_price * 100, 2) if h.buy_price else 0
    if stop_loss_price and stop_loss_price > 0:
        distance_pct = round((h.current_price - stop_loss_price) / stop_loss_price * 100, 2)
    else:
        distance_pct = 0
    h.stop_loss_price = stop_loss_price
    return profit_loss_pct, distance_pct


@router.post("", response_model=HoldingResponse)
def create_holding(data: HoldingCreate, db: Session = Depends(get_db)):
    ok, err = StopLossEngine.validate(data.buy_price, data.stop_loss_method, data.stop_loss_value)
    if not ok:
        raise HTTPException(status_code=422, detail=err)
    holding = Holding(
        code=data.code,
        name=data.name,
        type=data.type,
        buy_price=data.buy_price,
        quantity=data.quantity,
        buy_date=data.buy_date,
        highest_price=data.buy_price,
        stop_loss_method=data.stop_loss_method,
        stop_loss_value=data.stop_loss_value,
        current_price=data.buy_price,
        status="holding",
    )
    StopLossEngine.calculate(holding.buy_price, holding.highest_price, holding.stop_loss_method, holding.stop_loss_value)
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return holding


@router.get("")
def list_holdings(status: str = None, db: Session = Depends(get_db)):
    query = db.query(Holding)
    if status:
        query = query.filter(Holding.status == status)
    holdings = query.order_by(Holding.created_at.desc()).all()
    result = []
    for h in holdings:
        pnl, dist = _compute_fields(h)
        result.append({
            "id": h.id, "code": h.code, "name": h.name, "type": h.type,
            "buy_price": h.buy_price, "quantity": h.quantity, "buy_date": h.buy_date,
            "current_price": h.current_price, "stop_loss_method": h.stop_loss_method,
            "stop_loss_value": h.stop_loss_value, "stop_loss_price": h.stop_loss_price,
            "profit_loss_pct": pnl, "stop_loss_distance_pct": dist, "status": h.status,
        })
    return {"items": result, "total": len(result)}


@router.get("/{holding_id}", response_model=HoldingResponse)
def get_holding(holding_id: int, db: Session = Depends(get_db)):
    h = db.query(Holding).filter(Holding.id == holding_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="持仓不存在")
    StopLossEngine.calculate(h.buy_price, h.highest_price, h.stop_loss_method, h.stop_loss_value)
    return h


@router.put("/{holding_id}", response_model=HoldingResponse)
def update_holding(holding_id: int, data: HoldingUpdate, db: Session = Depends(get_db)):
    h = db.query(Holding).filter(Holding.id == holding_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="持仓不存在")
    if h.status == "stopped_out":
        raise HTTPException(status_code=400, detail="已止损的持仓不可修改")
    if data.name is not None:
        h.name = data.name
    if data.stop_loss_method is not None:
        h.stop_loss_method = data.stop_loss_method
    if data.stop_loss_value is not None:
        h.stop_loss_value = data.stop_loss_value
    if data.stop_loss_method is not None or data.stop_loss_value is not None:
        ok, err = StopLossEngine.validate(h.buy_price, h.stop_loss_method, h.stop_loss_value)
        if not ok:
            raise HTTPException(status_code=422, detail=err)
    db.commit()
    db.refresh(h)
    return h


@router.delete("/{holding_id}")
def delete_holding(holding_id: int, db: Session = Depends(get_db)):
    h = db.query(Holding).filter(Holding.id == holding_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="持仓不存在")
    db.delete(h)
    db.commit()
    return {"ok": True}


@router.post("/{holding_id}/close", response_model=HoldingResponse)
def close_holding(holding_id: int, data: HoldingClose, db: Session = Depends(get_db)):
    h = db.query(Holding).filter(Holding.id == holding_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="持仓不存在")
    if h.status == "stopped_out":
        raise HTTPException(status_code=400, detail="该持仓已平仓")
    h.status = "stopped_out"
    h.close_price = data.close_price
    db.commit()
    db.refresh(h)
    return h
