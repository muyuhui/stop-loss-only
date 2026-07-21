import json
import logging
from pathlib import Path

from config import AppConfig
from observability import JsonFormatter


ROOT = Path(__file__).resolve().parents[2]


def test_local_defaults_are_safe():
    config = AppConfig()
    assert config.bind_host == "127.0.0.1"
    assert config.scheduler_enabled in (True, False)
    assert config.readiness_timeout_seconds > 0


def test_structured_log_ignores_sensitive_extra_fields():
    record = logging.LogRecord("monitor", logging.INFO, __file__, 1, "cycle_completed", (), None)
    record.correlation_id = "safe-id"
    record.price = 123.45
    record.quantity = 1000
    payload = json.loads(JsonFormatter().format(record))
    assert payload["correlation_id"] == "safe-id"
    assert "price" not in payload and "quantity" not in payload


def test_start_script_never_kills_port_owner_and_stop_checks_ownership():
    start = (ROOT / "start.ps1").read_text(encoding="utf-8")
    stop = (ROOT / "stop.ps1").read_text(encoding="utf-8")
    assert "taskkill" not in start.lower()
    assert "Stop-Process" not in start
    assert "127.0.0.1" in start and "--reload" not in start
    assert "[switch]$Restart" in start and "stop.ps1" in start
    assert "if (-not $?)" in start
    assert "started_at" in stop and "root" in stop and "Stop-Process" in stop
    assert "Stop-LegacyRecordedProcess" in stop and "serviceMarker" in stop


def test_setup_is_separate_from_startup():
    start = (ROOT / "start.ps1").read_text(encoding="utf-8")
    setup = (ROOT / "setup.ps1").read_text(encoding="utf-8")
    assert "pip install" not in start and "npm install" not in start and "npm ci" not in start
    assert "pip install" in setup and "npm ci" in setup
