from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import config


MARKET_TIMEZONE = ZoneInfo(config.timezone)


def as_utc(value: datetime | None) -> datetime | None:
    """Attach UTC semantics to SQLite's naive server timestamps."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def as_market_time(value: datetime | None) -> datetime | None:
    """Restore the configured market timezone stripped by SQLite."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=MARKET_TIMEZONE)
    return value.astimezone(MARKET_TIMEZONE)
