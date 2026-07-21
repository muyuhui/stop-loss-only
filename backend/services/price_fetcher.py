from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from config import config
from services.market_clock import MARKET_TZ, is_in_trading_session, local_now, normalize_trade_date
from services.stop_loss import to_decimal


logger = logging.getLogger(__name__)


def trading_day_status(check_date: date | None = None) -> tuple[bool, bool]:
    check_date = check_date or local_now().date()
    try:
        import akshare as ak
        calendar = ak.tool_trade_date_hist_sina()
        days = {normalize_trade_date(value) for value in calendar["trade_date"].tolist()}
        return check_date in days, False
    except Exception as exc:
        logger.warning("交易日历获取失败，使用工作日退化规则: %s", exc)
        return check_date.weekday() < 5, True


def is_trading_day(check_date: date | None = None) -> bool:
    return trading_day_status(check_date)[0]


def is_market_open(now: datetime | None = None) -> tuple[bool, bool]:
    current = local_now(now)
    trading_day, degraded = trading_day_status(current.date())
    return trading_day and is_in_trading_session(current), degraded


def _error(code: str, asset_type: str, message: str, fetched_at: datetime, source: str = "akshare") -> dict:
    return {
        "code": code, "asset_type": asset_type, "current_price": None, "change_pct": None,
        "source": source, "quoted_at": None, "fetched_at": fetched_at,
        "fresh": False, "error": message,
    }


def _quote(code: str, asset_type: str, price, change_pct, source: str, quoted_at: datetime, fetched_at: datetime) -> dict:
    max_age = timedelta(days=3) if source == "akshare-open-fund-nav" else timedelta(seconds=config.quote_max_age_seconds)
    age = fetched_at.astimezone(MARKET_TZ) - quoted_at.astimezone(MARKET_TZ)
    return {
        "code": code, "asset_type": asset_type, "current_price": to_decimal(price),
        "change_pct": float(change_pct or 0), "source": source, "quoted_at": quoted_at,
        "fetched_at": fetched_at, "fresh": timedelta(0) <= age <= max_age, "error": None,
    }


def _rows_by_code(frame) -> dict[str, object]:
    if frame is None or frame.empty:
        return {}
    return {str(row["代码"]).zfill(6): row for _, row in frame.iterrows()}


def fetch_all_prices(holdings: list, now: datetime | None = None) -> list[dict]:
    fetched_at = local_now(now)
    unique = {(h.type, str(h.code).zfill(6)) for h in holdings}
    if not unique:
        return []
    if config.fixture_price is not None:
        return [_quote(code, asset_type, config.fixture_price, 0, "fixture", fetched_at, fetched_at) for asset_type, code in sorted(unique)]
    try:
        import akshare as ak
    except Exception as exc:
        return [_error(code, asset_type, str(exc), fetched_at) for asset_type, code in sorted(unique)]

    stock_rows, etf_rows, lof_rows = {}, {}, {}
    dataset_errors: dict[str, str] = {}
    if any(asset_type == "stock" for asset_type, _ in unique):
        try:
            stock_rows = _rows_by_code(ak.stock_zh_a_spot_em())
        except Exception as exc:
            dataset_errors["stock"] = str(exc)
    if any(asset_type == "fund" for asset_type, _ in unique):
        try:
            etf_rows = _rows_by_code(ak.fund_etf_spot_em())
        except Exception as exc:
            dataset_errors["etf"] = str(exc)
        try:
            lof_rows = _rows_by_code(ak.fund_lof_spot_em())
        except Exception as exc:
            dataset_errors["lof"] = str(exc)

    results = []
    for asset_type, code in sorted(unique):
        if asset_type == "stock":
            row = stock_rows.get(code)
            if row is not None:
                results.append(_quote(code, asset_type, row["最新价"], row.get("涨跌幅", 0), "akshare-stock-spot", fetched_at, fetched_at))
            else:
                results.append(_error(code, asset_type, dataset_errors.get("stock", f"未找到股票 {code}"), fetched_at))
            continue
        row = etf_rows.get(code)
        if row is None:
            row = lof_rows.get(code)
        if row is not None:
            source = "akshare-etf-spot" if code in etf_rows else "akshare-lof-spot"
            results.append(_quote(code, asset_type, row["最新价"], row.get("涨跌幅", 0), source, fetched_at, fetched_at))
            continue
        try:
            nav = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
            if nav.empty:
                raise ValueError(f"未找到基金 {code}")
            latest = nav.iloc[-1]
            quote_day = normalize_trade_date(latest.iloc[0])
            quoted_at = datetime.combine(quote_day, datetime.min.time(), tzinfo=MARKET_TZ)
            results.append(_quote(code, asset_type, latest["单位净值"], 0, "akshare-open-fund-nav", quoted_at, fetched_at))
        except Exception as exc:
            message = str(exc) or dataset_errors.get("etf") or dataset_errors.get("lof") or f"未找到基金 {code}"
            results.append(_error(code, asset_type, message, fetched_at))
    return results


def fetch_price(code: str, asset_type: str) -> dict:
    class Instrument:
        pass
    item = Instrument()
    item.code, item.type = code, asset_type
    return fetch_all_prices([item])[0]
