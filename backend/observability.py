from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
        }
        for name in ("correlation_id", "cycle_id", "outcome", "duration_ms", "count", "error_class"):
            value = getattr(record, name, None)
            if value is not None:
                payload[name] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(mode: str = "json") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter() if mode == "json" else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        correlation_id = request.headers.get("x-correlation-id") or uuid.uuid4().hex
        started = time.perf_counter()
        try:
            response = await call_next(request)
            outcome = str(response.status_code)
        except Exception as exc:
            logging.getLogger("api").exception(
                "request_failed",
                extra={"correlation_id": correlation_id, "duration_ms": round((time.perf_counter() - started) * 1000, 2), "error_class": type(exc).__name__},
            )
            raise
        response.headers["x-correlation-id"] = correlation_id
        logging.getLogger("api").info(
            "request_completed",
            extra={"correlation_id": correlation_id, "outcome": outcome, "duration_ms": round((time.perf_counter() - started) * 1000, 2)},
        )
        return response
