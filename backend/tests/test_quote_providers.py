from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from services.fixture_adapters import FixtureCalendar, FixtureQuoteProvider
from services.market_clock import MARKET_TZ
from services.provider_adapters import AkshareMarketCalendar, AkshareQuoteProvider, ProviderCallPolicy
from services.quote_contracts import CalendarSource, MarketSession, ProviderErrorCode, ProviderFailure, QuoteState


NOW = datetime(2026, 7, 23, 10, 0, tzinfo=MARKET_TZ)


class Instrument:
    def __init__(self, code="000001", asset_type="stock"):
        self.code = code
        self.type = asset_type


class FakeAk:
    def __init__(self, *, stock=None, etf=None, lof=None, nav=None, days=None):
        self.stock = stock if stock is not None else pd.DataFrame([{"代码": "000001", "最新价": 9.8, "涨跌幅": 1.2}])
        self.etf = etf if etf is not None else pd.DataFrame(columns=["代码", "最新价"])
        self.lof = lof if lof is not None else pd.DataFrame(columns=["代码", "最新价"])
        self.nav = nav if nav is not None else pd.DataFrame([{"净值日期": "2026-07-22", "单位净值": 1.2345}])
        self.days = days if days is not None else pd.DataFrame({"trade_date": [date(2026, 7, 23)]})
        self.calls = {"stock": 0, "etf": 0, "lof": 0, "nav": 0, "calendar": 0}

    def stock_zh_a_spot_em(self):
        self.calls["stock"] += 1
        return self.stock

    def fund_etf_spot_em(self):
        self.calls["etf"] += 1
        return self.etf

    def fund_lof_spot_em(self):
        self.calls["lof"] += 1
        return self.lof

    def fund_open_fund_info_em(self, **_):
        self.calls["nav"] += 1
        return self.nav

    def tool_trade_date_hist_sina(self):
        self.calls["calendar"] += 1
        return self.days


def calendar(*, source=CalendarSource.AUTHORITATIVE, session=MarketSession.OPEN, trading_day=True):
    return FixtureCalendar(trading_day=trading_day, session=session, source=source).decide(NOW)


def test_decimal_contract_and_fixture_adapter_are_deterministic_and_isolated():
    fixture_source = Path(__file__).resolve().parents[1] / "services" / "fixture_adapters.py"
    text = fixture_source.read_text(encoding="utf-8").lower()
    assert "akshare" not in text and "socket" not in text and "provider_adapters" not in text
    quote = FixtureQuoteProvider("8.8000", now=NOW).fetch([Instrument()], calendar())[0]
    assert quote.current_price == Decimal("8.8000")
    assert quote.state is QuoteState.LIVE and quote.is_actionable


@pytest.mark.parametrize(
    ("frame", "error_code"),
    [
        (pd.DataFrame([{"证券代码": "000001", "最新价": 9.8}]), ProviderErrorCode.INVALID_SCHEMA.value),
        (pd.DataFrame(columns=["代码", "最新价"]), ProviderErrorCode.EMPTY_DATASET.value),
        (pd.DataFrame([{"代码": "000001", "最新价": "--"}]), ProviderErrorCode.INVALID_PRICE.value),
    ],
)
def test_provider_contract_rejects_renamed_empty_and_invalid_data(frame, error_code):
    quote = AkshareQuoteProvider(ak_module=FakeAk(stock=frame), now=NOW).fetch([Instrument()], calendar())[0]
    assert quote.state is QuoteState.ERROR
    assert quote.error_code == error_code
    assert quote.current_price is None
    assert "--" not in (quote.error or "")


def test_provider_maps_delayed_close_and_nav_states():
    delayed_time = (NOW - timedelta(minutes=2)).isoformat()
    stock = pd.DataFrame([{"代码": "000001", "最新价": 9.8, "行情时间": delayed_time}])
    delayed = AkshareQuoteProvider(ak_module=FakeAk(stock=stock), now=NOW).fetch([Instrument()], calendar())[0]
    assert delayed.state is QuoteState.DELAYED and delayed.is_actionable

    closed = AkshareQuoteProvider(ak_module=FakeAk(stock=stock), now=NOW).fetch(
        [Instrument()], calendar(session=MarketSession.CLOSED),
    )[0]
    assert closed.state is QuoteState.CLOSE and not closed.is_actionable

    nav = AkshareQuoteProvider(ak_module=FakeAk(), now=NOW).fetch([Instrument("000999", "fund")], calendar())[0]
    assert nav.state is QuoteState.NAV and nav.current_price == Decimal("1.2345") and nav.is_actionable


def test_weekday_fallback_requires_provider_verified_current_session_time():
    fallback = calendar(source=CalendarSource.WEEKDAY_FALLBACK)
    unverified = FixtureQuoteProvider("8.8", now=NOW, provider_session_verified=False).fetch([Instrument()], fallback)[0]
    verified = FixtureQuoteProvider("8.8", now=NOW, provider_session_verified=True).fetch([Instrument()], fallback)[0]
    assert not unverified.is_actionable
    assert verified.is_actionable


def test_calendar_authoritative_cache_holiday_and_weekday_fallback():
    AkshareMarketCalendar._cache.clear()
    fake = FakeAk(days=pd.DataFrame({"trade_date": [date(2026, 7, 22)]}))
    adapter = AkshareMarketCalendar(ak_module=fake)
    holiday = adapter.decide(NOW)
    assert holiday.source is CalendarSource.AUTHORITATIVE and not holiday.is_trading_day

    class BrokenAk(FakeAk):
        def tool_trade_date_hist_sina(self):
            raise RuntimeError("raw provider secret must be redacted")

    cached = AkshareMarketCalendar(
        ak_module=BrokenAk(), policy=ProviderCallPolicy(attempts=1, sleeper=lambda _: None),
    ).decide(NOW)
    assert cached.source is CalendarSource.VALID_CACHE

    AkshareMarketCalendar._cache.clear()
    fallback = AkshareMarketCalendar(
        ak_module=BrokenAk(), policy=ProviderCallPolicy(attempts=1, sleeper=lambda _: None),
    ).decide(NOW)
    assert fallback.source is CalendarSource.WEEKDAY_FALLBACK and fallback.degraded
    assert fallback.degraded_reason == ProviderErrorCode.UNAVAILABLE.value


def test_each_market_dataset_downloads_at_most_once_per_cycle():
    fake = FakeAk(stock=pd.DataFrame([
        {"代码": "000001", "最新价": 9.8}, {"代码": "000002", "最新价": 10.2},
    ]))
    quotes = AkshareQuoteProvider(ak_module=fake, now=NOW).fetch([Instrument(), Instrument("000002"), Instrument()], calendar())
    assert len(quotes) == 2
    assert fake.calls["stock"] == 1


def test_call_policy_times_out_and_opens_circuit_with_stable_errors():
    policy = ProviderCallPolicy(total_timeout=0.001, attempts=1, cooldown=60, sleeper=lambda _: None)

    def slow():
        import time
        time.sleep(0.03)

    with pytest.raises(ProviderFailure) as first:
        policy.run("slow", slow)
    with pytest.raises(ProviderFailure):
        policy.run("slow", slow)
    with pytest.raises(ProviderFailure) as third:
        policy.run("slow", slow)
    assert first.value.code is ProviderErrorCode.TIMEOUT
    assert third.value.code is ProviderErrorCode.CIRCUIT_OPEN
