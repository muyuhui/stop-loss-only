from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class AppConfig:
    database_url: str = os.getenv("STOP_LOSS_DATABASE_URL", f"sqlite:///{BASE_DIR / 'stop_loss.db'}")
    timezone: str = os.getenv("STOP_LOSS_TIMEZONE", "Asia/Shanghai")
    quote_max_age_seconds: int = int(os.getenv("STOP_LOSS_QUOTE_MAX_AGE", "900"))
    scheduler_enabled: bool = os.getenv("STOP_LOSS_SCHEDULER_ENABLED", "1") == "1"
    bind_host: str = os.getenv("STOP_LOSS_BIND_HOST", "127.0.0.1")
    backend_port: int = int(os.getenv("STOP_LOSS_BACKEND_PORT", "8001"))
    frontend_port: int = int(os.getenv("STOP_LOSS_FRONTEND_PORT", "5173"))
    log_format: str = os.getenv("STOP_LOSS_LOG_FORMAT", "json")
    readiness_timeout_seconds: int = int(os.getenv("STOP_LOSS_READINESS_TIMEOUT", "20"))
    shutdown_timeout_seconds: int = int(os.getenv("STOP_LOSS_SHUTDOWN_TIMEOUT", "30"))
    fixture_price: str | None = os.getenv("STOP_LOSS_FIXTURE_PRICE")
    temp_dir: Path = Path(os.getenv("STOP_LOSS_TEMP_DIR", str(BASE_DIR.parent / ".tmp")))
    provider_connect_timeout_seconds: float = float(os.getenv("STOP_LOSS_PROVIDER_CONNECT_TIMEOUT", "3"))
    # AkShare's ETF spot endpoint may take more than 30 seconds for a cold
    # download. A short timeout discards a valid intraday quote and silently
    # replaces it with the previous day's fund NAV.
    provider_total_timeout_seconds: float = float(os.getenv("STOP_LOSS_PROVIDER_TOTAL_TIMEOUT", "45"))
    provider_max_attempts: int = int(os.getenv("STOP_LOSS_PROVIDER_MAX_ATTEMPTS", "2"))
    provider_circuit_cooldown_seconds: int = int(os.getenv("STOP_LOSS_PROVIDER_CIRCUIT_COOLDOWN", "60"))
    calendar_cache_seconds: int = int(os.getenv("STOP_LOSS_CALENDAR_CACHE_SECONDS", "86400"))
    refresh_lock_timeout_seconds: float = float(os.getenv("STOP_LOSS_REFRESH_LOCK_TIMEOUT", "2"))


config = AppConfig()
