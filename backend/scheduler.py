import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from database import SessionLocal
from services.monitoring import run_monitoring_cycle


logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def monitoring_job():
    db = SessionLocal()
    try:
        result = run_monitoring_cycle(db, scheduled=True)
        logger.info("监控周期结束 cycle=%s status=%s processed=%s triggered=%s", result["cycle_id"], result["status"], result["processed"], len(result["triggered"]))
    except Exception:
        db.rollback()
        logger.exception("监控周期异常")
    finally:
        db.close()


def start_scheduler(interval_minutes: int = 5):
    scheduler.add_job(monitoring_job, IntervalTrigger(minutes=interval_minutes), id="price_monitor", replace_existing=True, max_instances=1, coalesce=True)
    if not scheduler.running:
        scheduler.start()
        logger.info("定时监控已启动，间隔 %s 分钟", interval_minutes)


def update_interval(minutes: int):
    if not 1 <= minutes <= 60:
        raise ValueError("监控间隔必须在 1-60 分钟之间")
    if scheduler.get_job("price_monitor") is None:
        scheduler.add_job(monitoring_job, IntervalTrigger(minutes=minutes), id="price_monitor", replace_existing=True, max_instances=1, coalesce=True)
    else:
        scheduler.reschedule_job("price_monitor", trigger=IntervalTrigger(minutes=minutes))


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=True)
