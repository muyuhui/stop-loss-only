# -*- coding: utf-8 -*-
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import date
from database import SessionLocal
from models import Holding, Alert
from services.price_fetcher import fetch_all_prices, is_trading_day
from services.stop_loss import StopLossEngine
import logging

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()
_first_fetch_date = None


def monitoring_job():
    global _first_fetch_date
    today = date.today()
    is_td = is_trading_day(today)
    if not is_td:
        if _first_fetch_date == today:
            logger.info("非交易日且今日已获取过数据，跳过监控")
            return
        logger.info("非交易日首次启动，获取一次数据")
        _first_fetch_date = today
    db = SessionLocal()
    try:
        holdings = db.query(Holding).filter(Holding.status == "holding").all()
        if not holdings:
            return
        logger.info(f"开始监控 {len(holdings)} 个持仓")
        price_results = fetch_all_prices(holdings)
        for pr in price_results:
            h = next((x for x in holdings if x.code == pr["code"]), None)
            if h is None:
                continue
            if pr.get("error") is None and pr["current_price"] > 0:
                h.current_price = pr["current_price"]
                if pr["current_price"] > h.highest_price:
                    h.highest_price = pr["current_price"]
            sp = StopLossEngine.calculate(h.buy_price, h.highest_price, h.stop_loss_method, h.stop_loss_value)
            h.stop_loss_price = sp
            cp = h.current_price or pr.get("current_price", 0)
            if StopLossEngine.is_triggered(cp, sp):
                h.status = "stopped_out"
                alert = Alert(holding_id=h.id, trigger_price=sp, current_price=cp)
                db.add(alert)
                logger.info(f"止损触发: {h.name}({h.code}) 价格 {cp} <= {sp}")
        db.commit()
    except Exception as e:
        logger.error(f"监控任务异常: {e}")
        db.rollback()
    finally:
        db.close()


def start_scheduler(interval_minutes: int = 5):
    scheduler.add_job(
        monitoring_job,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="price_monitor",
        replace_existing=True,
    )
    if not scheduler.running:
        scheduler.start()
        logger.info(f"定时监控已启动，间隔 {interval_minutes} 分钟")


def update_interval(minutes: int):
    scheduler.reschedule_job(
        "price_monitor",
        trigger=IntervalTrigger(minutes=minutes),
    )
    logger.info(f"监控间隔已更新为 {minutes} 分钟")
