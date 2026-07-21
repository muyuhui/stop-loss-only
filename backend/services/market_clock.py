from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from config import config


MARKET_TZ = ZoneInfo(config.timezone)
SESSIONS = ((time(9, 30), time(11, 30)), (time(13, 0), time(15, 0)))


def normalize_trade_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip().replace("/", "-")
    if len(text) == 8 and text.isdigit():
        return datetime.strptime(text, "%Y%m%d").date()
    return datetime.fromisoformat(text).date()


def local_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(MARKET_TZ)
    if now.tzinfo is None:
        return now.replace(tzinfo=MARKET_TZ)
    return now.astimezone(MARKET_TZ)


def is_in_trading_session(now: datetime | None = None) -> bool:
    current = local_now(now).time().replace(tzinfo=None)
    return any(start <= current <= end for start, end in SESSIONS)
