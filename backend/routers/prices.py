from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db
from models import Holding, Alert
from services.price_fetcher import fetch_all_prices, is_trading_day, fetch_price
from services.stop_loss import StopLossEngine

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("")
def get_prices(db: Session = Depends(get_db)):
    holdings = db.query(Holding).filter(Holding.status == "holding").all()
    results = []
    for h in holdings:
        results.append({
            "code": h.code,
            "name": h.name,
            "current_price": h.current_price,
            "change_pct": 0,
            "fetched_at": datetime.now().isoformat(),
        })
    return {"items": results}


@router.post("/refresh")
def refresh_prices(db: Session = Depends(get_db)):
    if not is_trading_day():
        return {"ok": True, "message": "非交易日，跳过刷新"}
    holdings = db.query(Holding).filter(Holding.status == "holding").all()
    if not holdings:
        return {"ok": True, "message": "无活跃持仓"}
    price_results = fetch_all_prices(holdings)
    triggered = []
    for pr in price_results:
        h = next((x for x in holdings if x.code == pr["code"]), None)
        if h is None:
            continue
        if pr.get("error") is None and pr["current_price"] > 0:
            h.current_price = pr["current_price"]
            if pr["current_price"] > h.highest_price:
                h.highest_price = pr["current_price"]
        stop_loss_price = StopLossEngine.calculate(h.buy_price, h.highest_price, h.stop_loss_method, h.stop_loss_value)
        h.stop_loss_price = stop_loss_price
        if StopLossEngine.is_triggered(h.current_price or pr.get("current_price", 0), stop_loss_price):
            h.status = "stopped_out"
            alert = Alert(
                holding_id=h.id,
                trigger_price=stop_loss_price,
                current_price=h.current_price or pr.get("current_price", 0),
            )
            db.add(alert)
            triggered.append({"code": h.code, "name": h.name, "current_price": h.current_price, "stop_loss_price": stop_loss_price})
    db.commit()
    return {"ok": True, "triggered": triggered, "total": len(holdings), "trading_day": True}
