from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Protocol, Sequence


class QuoteState(str, Enum):
    UNPRICED = "unpriced"
    LIVE = "live"
    DELAYED = "delayed"
    CLOSE = "close"
    NAV = "nav"
    STALE = "stale"
    ERROR = "error"


class MarketSession(str, Enum):
    PRE_MARKET = "pre_market"
    OPEN = "open"
    LUNCH = "lunch"
    CLOSED = "closed"


class CalendarSource(str, Enum):
    AUTHORITATIVE = "authoritative"
    VALID_CACHE = "valid_cache"
    WEEKDAY_FALLBACK = "weekday_fallback"


class ProviderErrorCode(str, Enum):
    IMPORT_FAILED = "provider_import_failed"
    TIMEOUT = "provider_timeout"
    CIRCUIT_OPEN = "provider_circuit_open"
    UNAVAILABLE = "provider_unavailable"
    INVALID_SCHEMA = "provider_invalid_schema"
    EMPTY_DATASET = "provider_empty_dataset"
    INVALID_PRICE = "provider_invalid_price"
    NOT_FOUND = "quote_not_found"
    CALENDAR_UNAVAILABLE = "calendar_unavailable"
    DATABASE_BUSY = "database_busy"
    REFRESH_BUSY = "refresh_busy"
    INSTRUMENT_FAILED = "instrument_failed"


class ProviderFailure(RuntimeError):
    def __init__(self, code: ProviderErrorCode, *, retryable: bool = False):
        super().__init__(code.value)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class CalendarDecision:
    check_date: date
    is_trading_day: bool
    session: MarketSession
    source: CalendarSource
    checked_at: datetime
    degraded_reason: str | None = None

    @property
    def market_open(self) -> bool:
        return self.is_trading_day and self.session is MarketSession.OPEN

    @property
    def degraded(self) -> bool:
        return self.source is CalendarSource.WEEKDAY_FALLBACK


@dataclass(frozen=True)
class NormalizedQuote:
    code: str
    asset_type: str
    current_price: Decimal | None
    change_pct: Decimal | None
    state: QuoteState
    source: str
    quoted_at: datetime | None
    fetched_at: datetime
    fresh_until: datetime | None
    is_actionable: bool
    error_code: str | None = None
    error: str | None = None
    provider_session_verified: bool = False

    @property
    def fresh(self) -> bool:
        return self.state not in {QuoteState.UNPRICED, QuoteState.STALE, QuoteState.ERROR}

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "asset_type": self.asset_type,
            "current_price": self.current_price,
            "change_pct": float(self.change_pct) if self.change_pct is not None else None,
            "state": self.state.value,
            "source": self.source,
            "quoted_at": self.quoted_at,
            "fetched_at": self.fetched_at,
            "fresh_until": self.fresh_until,
            "is_actionable": self.is_actionable,
            "fresh": self.fresh,
            "error_code": self.error_code,
            "error": self.error,
        }


class Clock(Protocol):
    def now(self) -> datetime: ...


class QuoteProvider(Protocol):
    def fetch(self, instruments: Sequence[object], calendar: CalendarDecision) -> list[NormalizedQuote]: ...


class MarketCalendar(Protocol):
    def decide(self, now: datetime | None = None) -> CalendarDecision: ...
