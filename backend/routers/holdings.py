from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from database import get_db
from models import Holding
from schemas import HoldingClose, HoldingCreate, HoldingHistoryResponse, HoldingPage, HoldingResponse, HoldingUpdate
from services.price_history import HistoryUnavailable, holding_history
from services.presentation import holding_payload
from services.stop_loss import StopLossEngine, to_decimal


router = APIRouter(prefix="/holdings", tags=["holdings"])


def _get_holding(db: Session, holding_id: int) -> Holding:
    holding = db.query(Holding).filter(Holding.id == holding_id).first()
    if not holding:
        raise HTTPException(status_code=404, detail="持仓不存在")
    return holding


@router.post("", response_model=HoldingResponse, status_code=201)
def create_holding(data: HoldingCreate, db: Session = Depends(get_db)):
    ok, error = StopLossEngine.validate(data.buy_price, data.stop_loss_method, data.stop_loss_value)
    if not ok:
        raise HTTPException(status_code=422, detail=error)
    holding = Holding(
        code=data.code.strip().zfill(6), name=data.name.strip(), type=data.type,
        buy_price=to_decimal(data.buy_price), quantity=data.quantity, buy_date=data.buy_date,
        current_price=to_decimal(data.buy_price), highest_price=to_decimal(data.buy_price),
        stop_loss_method=data.stop_loss_method, stop_loss_value=to_decimal(data.stop_loss_value),
        status="holding",
    )
    holding.stop_loss_price = StopLossEngine.calculate(holding.buy_price, holding.highest_price, holding.stop_loss_method, holding.stop_loss_value)
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return holding_payload(holding)


@router.get("", response_model=HoldingPage)
def list_holdings(
    status_filter: str | None = Query(None, alias="status", pattern="^(holding|triggered|closed)$"),
    page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db),
):
    query = db.query(Holding)
    if status_filter:
        query = query.filter(Holding.status == status_filter)
    total = query.count()
    items = query.order_by(Holding.created_at.desc(), Holding.id.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": [holding_payload(item) for item in items], "total": total, "page": page, "size": size}


@router.get("/{holding_id}", response_model=HoldingResponse)
def get_holding(holding_id: int, db: Session = Depends(get_db)):
    return holding_payload(_get_holding(db, holding_id))


@router.get("/{holding_id}/history", response_model=HoldingHistoryResponse)
def get_holding_history(
    holding_id: int,
    range_name: str = Query("3m", alias="range", pattern="^(1m|3m|6m|1y)$"),
    db: Session = Depends(get_db),
):
    holding = _get_holding(db, holding_id)
    try:
        return holding_history(db, holding, range_name)
    except HistoryUnavailable as exc:
        raise HTTPException(status_code=503, detail={
            "message": "历史行情暂时不可用", "correlation_id": exc.correlation_id,
        }) from exc


@router.put("/{holding_id}", response_model=HoldingResponse)
def update_holding(holding_id: int, data: HoldingUpdate, db: Session = Depends(get_db)):
    holding = _get_holding(db, holding_id)
    if holding.status != "holding":
        raise HTTPException(status_code=400, detail="只有持有中的持仓可以修改止损设置")
    prospective_method = data.stop_loss_method or holding.stop_loss_method
    prospective_value = data.stop_loss_value if data.stop_loss_value is not None else holding.stop_loss_value
    ok, error = StopLossEngine.validate(holding.buy_price, prospective_method, prospective_value)
    if not ok:
        raise HTTPException(status_code=422, detail=error)
    if data.name is not None:
        holding.name = data.name.strip()
    holding.stop_loss_method = prospective_method
    holding.stop_loss_value = to_decimal(prospective_value)
    holding.stop_loss_price = StopLossEngine.calculate(holding.buy_price, holding.highest_price, prospective_method, prospective_value)
    db.commit()
    db.refresh(holding)
    return holding_payload(holding)


@router.delete("/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holding(holding_id: int, db: Session = Depends(get_db)):
    holding = _get_holding(db, holding_id)
    if holding.status == "triggered":
        raise HTTPException(status_code=400, detail="请先处理已触发的持仓")
    db.delete(holding)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{holding_id}/close", response_model=HoldingResponse)
def close_holding(holding_id: int, data: HoldingClose, db: Session = Depends(get_db)):
    holding = _get_holding(db, holding_id)
    if holding.status == "closed":
        raise HTTPException(status_code=400, detail="该持仓已经关闭")
    holding.status = "closed"
    holding.close_price = to_decimal(data.close_price)
    db.commit()
    db.refresh(holding)
    return holding_payload(holding)
