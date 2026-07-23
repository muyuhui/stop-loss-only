from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from config import config
from database import SessionLocal, engine
from migrations import LATEST_SCHEMA_VERSION, current_version
from routers import alerts, dashboard, holdings, monitoring, operations, positions, prices, settings
from scheduler import scheduler, start_scheduler, stop_scheduler
from routers.settings import get_effective_settings
from observability import RequestLoggingMiddleware, configure_logging
from network_guard import install_from_environment


install_from_environment()
configure_logging(config.log_format)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if current_version(engine) == LATEST_SCHEMA_VERSION and config.scheduler_enabled:
        db = SessionLocal()
        try:
            interval = get_effective_settings(db)["monitor_interval"]
        finally:
            db.close()
        start_scheduler(interval)
    yield
    stop_scheduler()


def create_app() -> FastAPI:
    application = FastAPI(title="止损不止盈", version="2.0.0", lifespan=lifespan)
    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(
        CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
    )
    for router in (holdings.router, positions.router, prices.router, alerts.router, dashboard.router, settings.router, monitoring.router, operations.router):
        application.include_router(router, prefix="/api")

    @application.get("/api/health/live")
    def live():
        return {"status": "ok"}

    @application.get("/api/health/ready")
    def ready(response: Response):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            version = current_version(engine)
            if version != LATEST_SCHEMA_VERSION:
                response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
                return {"status": "not_ready", "reason": "database migration required", "schema_version": version}
            return {"status": "ok", "schema_version": version, "scheduler_running": scheduler.running if config.scheduler_enabled else False}
        except Exception:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "not_ready", "reason": "database unavailable"}

    @application.get("/api/health")
    def health():
        return {"status": "ok"}
    return application


app = create_app()
