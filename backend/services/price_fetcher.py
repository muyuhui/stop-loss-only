from __future__ import annotations

import logging
from datetime import date, datetime

from config import config
from services.fixture_adapters import FixtureCalendar, FixtureQuoteProvider
from services.market_clock import local_now, normalize_trade_date
from services.provider_adapters import AkshareMarketCalendar, AkshareQuoteProvider
from services.quote_contracts import MarketSession
from services.stop_loss import to_decimal


logger = logging.getLogger(__name__)


def _history_rows(frame, date_column: str, price_column: str, source: str) -> list[dict]:
    if frame is None or frame.empty:
        return []
    rows = {}
    for _, row in frame.iterrows():
        trade_date = normalize_trade_date(row[date_column])
        price = to_decimal(row[price_column])
        if price > 0:
            rows[trade_date] = {"trade_date": trade_date, "price": price, "source": source}
    return [rows[key] for key in sorted(rows)]


def fetch_price_history(code: str, asset_type: str, start_date: date, end_date: date) -> list[dict]:
    """Fetch normalized daily close/NAV history from AkShare."""
    if config.fixture_price is not None:
        return [{"trade_date": end_date, "price": to_decimal(config.fixture_price), "source": "fixture"}]
    import akshare as ak

    start, end = start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d")
    if asset_type == "stock":
        frame = ak.stock_zh_a_hist(symbol=str(code).zfill(6), period="daily", start_date=start, end_date=end, adjust="")
        return _history_rows(frame, "日期", "收盘", "akshare-stock-history")

    try:
        frame = ak.fund_etf_hist_em(symbol=str(code).zfill(6), period="daily", start_date=start, end_date=end, adjust="")
        rows = _history_rows(frame, "日期", "收盘", "akshare-etf-history")
        if rows:
            return rows
    except Exception:
        logger.info("ETF 历史接口未返回 %s，尝试开放式基金净值", code)
    frame = ak.fund_open_fund_info_em(symbol=str(code).zfill(6), indicator="单位净值走势")
    rows = _history_rows(frame, "净值日期", "单位净值", "akshare-open-fund-history")
    return [row for row in rows if start_date <= row["trade_date"] <= end_date]


def trading_day_status(check_date: date | None = None) -> tuple[bool, bool]:
    checked_at = local_now()
    if check_date is not None:
        checked_at = checked_at.replace(year=check_date.year, month=check_date.month, day=check_date.day)
    decision = AkshareMarketCalendar().decide(checked_at)
    return decision.is_trading_day, decision.degraded


def is_trading_day(check_date: date | None = None) -> bool:
    return trading_day_status(check_date)[0]


def is_market_open(now: datetime | None = None) -> tuple[bool, bool]:
    calendar = FixtureCalendar() if config.fixture_price is not None else AkshareMarketCalendar()
    decision = calendar.decide(now)
    return decision.market_open, decision.degraded


def fetch_all_prices(holdings: list, now: datetime | None = None, *, provider=None, calendar=None) -> list[dict]:
    if not holdings:
        return []
    if calendar is None:
        calendar = FixtureCalendar(session=MarketSession.OPEN) if config.fixture_price is not None else AkshareMarketCalendar()
    decision = calendar.decide(now)
    if provider is None:
        provider = FixtureQuoteProvider(config.fixture_price, now=now) if config.fixture_price is not None else AkshareQuoteProvider(now=now)
    return [quote.as_dict() for quote in provider.fetch(holdings, decision)]


def fetch_price(code: str, asset_type: str) -> dict:
    class Instrument:
        pass
    item = Instrument()
    item.code, item.type = code, asset_type
    return fetch_all_prices([item])[0]
