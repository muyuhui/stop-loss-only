from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Mapping, Sequence

from services.market_clock import local_now, market_session
from services.quote_contracts import CalendarDecision, CalendarSource, MarketSession, NormalizedQuote, QuoteState
from services.stop_loss import to_decimal


class FixtureCalendar:
    """Deterministic calendar with no production-provider imports."""

    def __init__(self, *, trading_day: bool = True, session: MarketSession = MarketSession.OPEN, source: CalendarSource = CalendarSource.AUTHORITATIVE):
        self.trading_day = trading_day
        self.session = session
        self.source = source

    def decide(self, now: datetime | None = None) -> CalendarDecision:
        checked_at = local_now(now)
        return CalendarDecision(
            check_date=checked_at.date(), is_trading_day=self.trading_day,
            session=self.session, source=self.source, checked_at=checked_at,
            degraded_reason="fixture_weekday_fallback" if self.source is CalendarSource.WEEKDAY_FALLBACK else None,
        )


class FixtureQuoteProvider:
    """Deterministic in-memory quote adapter for hermetic tests."""

    def __init__(self, prices: Decimal | str | Mapping[tuple[str, str], Decimal | str], *, now: datetime | None = None, state: QuoteState = QuoteState.LIVE, provider_session_verified: bool = True):
        self.prices = prices
        self.fixed_now = now
        self.state = state
        self.provider_session_verified = provider_session_verified

    def fetch(self, instruments: Sequence[object], calendar: CalendarDecision) -> list[NormalizedQuote]:
        fetched_at = local_now(self.fixed_now or calendar.checked_at)
        unique = sorted({(str(item.type), str(item.code).zfill(6)) for item in instruments})
        results = []
        for asset_type, code in unique:
            raw = self.prices.get((asset_type, code)) if isinstance(self.prices, Mapping) else self.prices
            if raw is None:
                results.append(NormalizedQuote(
                    code, asset_type, None, None, QuoteState.ERROR, "fixture", None, fetched_at, None,
                    False, "quote_not_found", "fixture quote missing",
                ))
                continue
            state = self.state
            fresh_until = fetched_at + (timedelta(days=3) if state is QuoteState.NAV else timedelta(seconds=900))
            actionable_state = state in {QuoteState.LIVE, QuoteState.DELAYED, QuoteState.NAV}
            fallback_allowed = self.provider_session_verified and fetched_at.date() == calendar.check_date and market_session(fetched_at) is MarketSession.OPEN
            calendar_allowed = calendar.source is not CalendarSource.WEEKDAY_FALLBACK or fallback_allowed
            results.append(NormalizedQuote(
                code, asset_type, to_decimal(raw), Decimal("0"), state, "fixture",
                fetched_at, fetched_at, fresh_until, actionable_state and calendar_allowed,
                provider_session_verified=self.provider_session_verified,
            ))
        return results
