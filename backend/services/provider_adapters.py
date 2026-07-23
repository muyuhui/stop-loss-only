from __future__ import annotations

import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import date, datetime, time as day_time, timedelta
from decimal import Decimal, InvalidOperation
from threading import Lock
from typing import Callable, Sequence

from config import config
from services.market_clock import MARKET_TZ, local_now, market_session, normalize_trade_date
from services.quote_contracts import (
    CalendarDecision,
    CalendarSource,
    MarketSession,
    NormalizedQuote,
    ProviderErrorCode,
    ProviderFailure,
    QuoteState,
)
from services.stop_loss import to_decimal


logger = logging.getLogger(__name__)


class ProviderCallPolicy:
    """Hard total timeout, bounded retries with jitter, and a small circuit breaker."""

    def __init__(self, *, total_timeout: float | None = None, attempts: int | None = None, cooldown: int | None = None, sleeper: Callable[[float], None] = time.sleep):
        self.total_timeout = total_timeout or config.provider_total_timeout_seconds
        self.attempts = attempts or config.provider_max_attempts
        self.cooldown = cooldown or config.provider_circuit_cooldown_seconds
        self.sleeper = sleeper
        self._failures: dict[str, int] = {}
        self._open_until: dict[str, float] = {}
        self._lock = Lock()

    def run(self, key: str, operation: Callable[[], object]):
        monotonic = time.monotonic()
        with self._lock:
            if self._open_until.get(key, 0) > monotonic:
                raise ProviderFailure(ProviderErrorCode.CIRCUIT_OPEN)
        last: ProviderFailure | None = None
        for attempt in range(self.attempts):
            executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"provider-{key}")
            future = executor.submit(operation)
            try:
                result = future.result(timeout=self.total_timeout)
                with self._lock:
                    self._failures.pop(key, None)
                    self._open_until.pop(key, None)
                return result
            except FutureTimeout:
                future.cancel()
                last = ProviderFailure(ProviderErrorCode.TIMEOUT, retryable=True)
            except ProviderFailure as exc:
                last = exc
            except Exception:
                last = ProviderFailure(ProviderErrorCode.UNAVAILABLE, retryable=True)
            finally:
                executor.shutdown(wait=False, cancel_futures=True)
            # A Python worker already executing a timed-out provider call
            # cannot be cancelled. Retrying it immediately starts a second
            # expensive download and can make every later refresh slower.
            if last and (not last.retryable or last.code is ProviderErrorCode.TIMEOUT or attempt + 1 >= self.attempts):
                break
            self.sleeper(0.025 * (2 ** attempt) + random.uniform(0, 0.025))
        with self._lock:
            failures = self._failures.get(key, 0) + 1
            self._failures[key] = failures
            if failures >= 2:
                self._open_until[key] = time.monotonic() + self.cooldown
        assert last is not None
        logger.warning("provider_call_failed", extra={"outcome": last.code.value, "error_class": type(last).__name__})
        raise last


class AkshareMarketCalendar:
    _cache: dict[str, tuple[frozenset[date], datetime]] = {}
    _cache_lock = Lock()

    def __init__(self, *, policy: ProviderCallPolicy | None = None, ak_module=None):
        self.policy = policy or ProviderCallPolicy()
        self.ak_module = ak_module

    def _download(self) -> frozenset[date]:
        if self.ak_module is None:
            try:
                import akshare as ak
            except Exception as exc:
                raise ProviderFailure(ProviderErrorCode.IMPORT_FAILED) from exc
        else:
            ak = self.ak_module
        frame = ak.tool_trade_date_hist_sina()
        if frame is None or frame.empty:
            raise ProviderFailure(ProviderErrorCode.EMPTY_DATASET, retryable=True)
        if "trade_date" not in frame.columns:
            raise ProviderFailure(ProviderErrorCode.INVALID_SCHEMA)
        return frozenset(normalize_trade_date(value) for value in frame["trade_date"].tolist())

    def decide(self, now: datetime | None = None) -> CalendarDecision:
        checked_at = local_now(now)
        cache_key = "cn"
        source = CalendarSource.AUTHORITATIVE
        reason = None
        try:
            days = self.policy.run("calendar-cn", self._download)
            with self._cache_lock:
                self._cache[cache_key] = (days, checked_at + timedelta(seconds=config.calendar_cache_seconds))
        except ProviderFailure as exc:
            with self._cache_lock:
                cached = self._cache.get(cache_key)
            if cached and cached[1] >= checked_at:
                days = cached[0]
                source = CalendarSource.VALID_CACHE
                reason = exc.code.value
            else:
                source = CalendarSource.WEEKDAY_FALLBACK
                reason = exc.code.value
                days = frozenset({checked_at.date()}) if checked_at.weekday() < 5 else frozenset()
        return CalendarDecision(
            check_date=checked_at.date(), is_trading_day=checked_at.date() in days,
            session=market_session(checked_at), source=source, checked_at=checked_at,
            degraded_reason=reason,
        )


class AkshareQuoteProvider:
    def __init__(self, *, policy: ProviderCallPolicy | None = None, ak_module=None, now: datetime | None = None, http_get=None):
        self.policy = policy or ProviderCallPolicy()
        self.ak_module = ak_module
        self.fixed_now = now
        self.http_get = http_get
        self._datasets: dict[str, object] = {}
        self._dataset_errors: dict[str, ProviderFailure] = {}

    def _ak(self):
        if self.ak_module is not None:
            return self.ak_module
        try:
            import akshare as ak
            return ak
        except Exception as exc:
            raise ProviderFailure(ProviderErrorCode.IMPORT_FAILED) from exc

    def _dataset(self, name: str, loader: Callable[[], object]):
        if name in self._datasets:
            return self._datasets[name]
        if name in self._dataset_errors:
            raise self._dataset_errors[name]
        try:
            frame = self.policy.run(name, loader)
            if frame is None or frame.empty:
                raise ProviderFailure(ProviderErrorCode.EMPTY_DATASET, retryable=True)
            required = {"代码", "最新价"}
            if not required.issubset(set(frame.columns)):
                raise ProviderFailure(ProviderErrorCode.INVALID_SCHEMA)
            self._datasets[name] = frame
            return frame
        except ProviderFailure as exc:
            self._dataset_errors[name] = exc
            raise

    @staticmethod
    def _rows_by_code(frame) -> dict[str, object]:
        return {str(row["代码"]).zfill(6): row for _, row in frame.iterrows()}

    @staticmethod
    def _quote_time(row, fallback: datetime) -> tuple[datetime, bool]:
        for column in ("行情时间", "更新时间", "时间"):
            value = row.get(column) if hasattr(row, "get") else None
            if value is None:
                continue
            try:
                parsed = datetime.fromisoformat(str(value))
                quoted = local_now(parsed)
                verified = quoted.date() == fallback.date() and market_session(quoted) is MarketSession.OPEN
                return quoted, verified
            except (TypeError, ValueError):
                continue
        return fallback, False

    @staticmethod
    def _error(code: str, asset_type: str, fetched_at: datetime, failure: ProviderFailure, source: str = "akshare") -> NormalizedQuote:
        return NormalizedQuote(
            code, asset_type, None, None, QuoteState.ERROR, source, None, fetched_at, None,
            False, failure.code.value, "行情提供方暂时不可用",
        )

    def _spot_quote(self, code: str, asset_type: str, row, source: str, calendar: CalendarDecision, fetched_at: datetime) -> NormalizedQuote:
        try:
            price = to_decimal(row["最新价"])
            if price <= 0:
                raise InvalidOperation
            change = Decimal(str(row.get("涨跌幅", 0) or 0))
        except (InvalidOperation, TypeError, ValueError):
            return self._error(code, asset_type, fetched_at, ProviderFailure(ProviderErrorCode.INVALID_PRICE), source)
        quoted_at, verified = self._quote_time(row, fetched_at)
        fresh_until = quoted_at + timedelta(seconds=config.quote_max_age_seconds)
        age = fetched_at - quoted_at
        if age < timedelta(0) or fetched_at > fresh_until:
            state = QuoteState.STALE
        elif not calendar.market_open:
            state = QuoteState.CLOSE
        elif age > timedelta(seconds=60):
            state = QuoteState.DELAYED
        else:
            state = QuoteState.LIVE
        fallback_allowed = verified and calendar.source is CalendarSource.WEEKDAY_FALLBACK
        calendar_allowed = calendar.source is not CalendarSource.WEEKDAY_FALLBACK or fallback_allowed
        return NormalizedQuote(
            code, asset_type, price, change, state, source, quoted_at, fetched_at, fresh_until,
            state in {QuoteState.LIVE, QuoteState.DELAYED} and calendar_allowed,
            provider_session_verified=verified,
        )

    def _nav_quote(self, code: str, frame, calendar: CalendarDecision, fetched_at: datetime) -> NormalizedQuote:
        if frame is None or frame.empty:
            return self._error(code, "fund", fetched_at, ProviderFailure(ProviderErrorCode.EMPTY_DATASET), "akshare-open-fund-nav")
        if not {"净值日期", "单位净值"}.issubset(set(frame.columns)):
            return self._error(code, "fund", fetched_at, ProviderFailure(ProviderErrorCode.INVALID_SCHEMA), "akshare-open-fund-nav")
        latest = frame.iloc[-1]
        try:
            price = to_decimal(latest["单位净值"])
            if price <= 0:
                raise InvalidOperation
            quote_day = normalize_trade_date(latest["净值日期"])
        except (InvalidOperation, TypeError, ValueError):
            return self._error(code, "fund", fetched_at, ProviderFailure(ProviderErrorCode.INVALID_PRICE), "akshare-open-fund-nav")
        quoted_at = datetime.combine(quote_day, day_time(15, 0), tzinfo=MARKET_TZ)
        fresh_until = quoted_at + timedelta(days=3)
        state = QuoteState.NAV if fetched_at <= fresh_until else QuoteState.STALE
        actionable = state is QuoteState.NAV and calendar.source is not CalendarSource.WEEKDAY_FALLBACK
        return NormalizedQuote(code, "fund", price, Decimal("0"), state, "akshare-open-fund-nav", quoted_at, fetched_at, fresh_until, actionable)

    def _direct_etf_quote(self, code: str, calendar: CalendarDecision, fetched_at: datetime) -> NormalizedQuote | None:
        """Fetch one ETF from Eastmoney instead of downloading the whole market."""
        # Unit tests pass an AkShare double and should remain fully hermetic.
        if self.ak_module is not None and self.http_get is None:
            return None
        if self.http_get is None:
            try:
                import requests
            except Exception:
                return None
            http_get = requests.get
        else:
            http_get = self.http_get

        markets = ("1", "0") if str(code).startswith(("5", "6")) else ("0", "1")
        for market in markets:
            def load(market=market):
                response = http_get(
                    "https://push2delay.eastmoney.com/api/qt/stock/get",
                    params={"secid": f"{market}.{code}", "fields": "f43,f57,f169,f170,f124"},
                    timeout=config.provider_total_timeout_seconds,
                )
                response.raise_for_status()
                return response.json().get("data") or {}

            try:
                payload = self.policy.run(f"etf-direct-{market}-{code}", load)
                if str(payload.get("f57", "")).zfill(6) != code:
                    continue
                # Eastmoney returns ETF prices as thousandths (for example
                # 1136 represents an ETF price of 1.136).
                price = to_decimal(Decimal(str(payload.get("f43", 0))) / Decimal("1000"))
                if price <= 0:
                    continue
                timestamp = payload.get("f124")
                quoted_at = fetched_at
                if timestamp:
                    try:
                        quoted_at = datetime.fromtimestamp(int(timestamp), tz=MARKET_TZ)
                    except (TypeError, ValueError, OSError):
                        pass
                change = Decimal(str(payload.get("f170", 0) or 0)) / Decimal("100")
                fresh_until = quoted_at + timedelta(seconds=config.quote_max_age_seconds)
                state = QuoteState.LIVE if calendar.market_open else QuoteState.CLOSE
                actionable = state is QuoteState.LIVE and calendar.source is not CalendarSource.WEEKDAY_FALLBACK
                return NormalizedQuote(code, "fund", price, change, state, "eastmoney-etf-spot", quoted_at, fetched_at, fresh_until, actionable)
            except (ProviderFailure, InvalidOperation, TypeError, ValueError):
                continue
        return None

    def fetch(self, instruments: Sequence[object], calendar: CalendarDecision) -> list[NormalizedQuote]:
        fetched_at = local_now(self.fixed_now or calendar.checked_at)
        unique = sorted({(str(item.type), str(item.code).zfill(6)) for item in instruments})
        ak = None
        try:
            ak = self._ak()
        except ProviderFailure as exc:
            return [self._error(code, asset_type, fetched_at, exc) for asset_type, code in unique]

        direct_etf_quotes = {
            code: quote for asset_type, code in unique if asset_type == "fund"
            if (quote := self._direct_etf_quote(code, calendar, fetched_at)) is not None
        }
        remaining = [(asset_type, code) for asset_type, code in unique if code not in direct_etf_quotes]
        rows: dict[str, dict[str, object]] = {}
        if any(asset_type == "stock" for asset_type, _ in remaining):
            try:
                rows["stock"] = self._rows_by_code(self._dataset("stock", lambda: ak.stock_zh_a_spot_em()))
            except ProviderFailure:
                rows["stock"] = {}

        # ETF and LOF share the legacy "fund" type.  Try the ETF feed first
        # and only download the LOF feed for codes absent from it.  Apart from
        # avoiding an expensive redundant request, this prevents a successful
        # ETF quote from being obscured by a later fallback attempt.
        fund_codes = {code for asset_type, code in remaining if asset_type == "fund"}
        if fund_codes:
            try:
                rows["etf"] = self._rows_by_code(self._dataset("etf", lambda: ak.fund_etf_spot_em()))
            except ProviderFailure:
                rows["etf"] = {}
            unresolved_fund_codes = fund_codes - set(rows["etf"])
            etf_failure = self._dataset_errors.get("etf")
            # Both endpoints download a full market table. If the ETF source
            # timed out, a LOF request would repeat the same expensive work
            # and make a manual refresh exceed its browser timeout.
            if unresolved_fund_codes and (etf_failure is None or etf_failure.code is not ProviderErrorCode.TIMEOUT):
                try:
                    rows["lof"] = self._rows_by_code(self._dataset("lof", lambda: ak.fund_lof_spot_em()))
                except ProviderFailure:
                    rows["lof"] = {}

        results: list[NormalizedQuote] = []
        for asset_type, code in unique:
            if code in direct_etf_quotes:
                results.append(direct_etf_quotes[code])
                continue
            if asset_type == "stock":
                row = rows.get("stock", {}).get(code)
                if row is None:
                    failure = self._dataset_errors.get("stock", ProviderFailure(ProviderErrorCode.NOT_FOUND))
                    results.append(self._error(code, asset_type, fetched_at, failure))
                else:
                    results.append(self._spot_quote(code, asset_type, row, "akshare-stock-spot", calendar, fetched_at))
                continue
            row = rows.get("etf", {}).get(code)
            if row is None:
                row = rows.get("lof", {}).get(code)
            if row is not None:
                source = "akshare-etf-spot" if code in rows.get("etf", {}) else "akshare-lof-spot"
                results.append(self._spot_quote(code, asset_type, row, source, calendar, fetched_at))
                continue
            try:
                nav = self.policy.run(f"nav-{code}", lambda code=code: ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势"))
                results.append(self._nav_quote(code, nav, calendar, fetched_at))
            except ProviderFailure as exc:
                results.append(self._error(code, asset_type, fetched_at, exc))
        return results
