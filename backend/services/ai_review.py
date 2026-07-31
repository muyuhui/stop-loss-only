from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from threading import Lock

from sqlalchemy.orm import Session

from models import Holding
from schemas import (
    AIReviewFact,
    AIReviewMetrics,
    AIReviewReason,
    AIReviewScenario,
    HoldingReviewResponse,
    HoldingReviewSnapshot,
    ProviderReviewReason,
)
from services.ai_provider import AIProvider
from services.market_clock import local_now
from services.price_history import analysis_history
from services.risk_budget import as_decimal, decimal_string, risk_budget_summary


HUNDRED = Decimal("100")
ZERO = Decimal("0")
_locks_guard = Lock()
_holding_locks: dict[int, Lock] = {}


class AIReviewError(RuntimeError):
    def __init__(self, error_code: str):
        super().__init__(error_code)
        self.error_code = error_code


def _pct(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.quantize(Decimal("0.01")), "f")


def _period_return(prices: list[Decimal], period: int) -> str | None:
    if len(prices) < period or prices[-period] <= 0:
        return None
    return _pct((prices[-1] / prices[-period] - 1) * HUNDRED)


def _metrics(points: list[dict]) -> AIReviewMetrics:
    prices = [as_decimal(point["price"]) for point in points]
    running_high = prices[0]
    max_drawdown = ZERO
    for price in prices:
        running_high = max(running_high, price)
        if running_high > 0:
            max_drawdown = min(max_drawdown, (price / running_high - 1) * HUNDRED)
    low, high, latest = min(prices), max(prices), prices[-1]
    range_position = None if high == low else (latest - low) / (high - low) * HUNDRED
    return AIReviewMetrics(
        return_5d_pct=_period_return(prices, 5),
        return_20d_pct=_period_return(prices, 20),
        return_60d_pct=_period_return(prices, 60),
        max_drawdown_pct=_pct(max_drawdown),
        range_position_pct=_pct(range_position),
    )


def _fact(
    fact_id: str,
    label: str,
    value,
    *,
    source: str,
    as_of=None,
) -> AIReviewFact:
    return AIReviewFact(
        fact_id=fact_id,
        label=label,
        value=None if value is None else str(value),
        as_of=None if as_of is None else str(as_of),
        source=source,
    )


def build_holding_review_snapshot(
    db: Session,
    holding: Holding,
    recent: dict,
    settings: dict,
    *,
    authority_stage: str,
) -> HoldingReviewSnapshot:
    current = as_decimal(holding.current_price)
    buy = as_decimal(holding.buy_price)
    quantity = as_decimal(holding.quantity)
    stop = as_decimal(holding.stop_loss_price)
    profit_pct = (current / buy - 1) * HUNDRED
    stop_distance_pct = (current - stop) / current * HUNDRED
    metrics = _metrics(recent["points"])
    budget = risk_budget_summary(db, settings, authority_stage=authority_stage)
    holding_risk = max(ZERO, (buy - stop) * quantity)
    equity = settings.get("portfolio_equity")
    position_limit = None
    if equity is not None:
        position_limit = (
            as_decimal(equity)
            * as_decimal(settings["default_position_risk_limit_pct"])
            / HUNDRED
        )
    facts = [
        _fact("holding.status", "持仓状态", holding.status, source="holding"),
        _fact("quote.current_price", "当前价", decimal_string(current), source="holding", as_of=holding.quoted_at),
        _fact("quote.state", "行情状态", holding.quote_state, source="holding", as_of=holding.quoted_at),
        _fact("holding.profit_loss_pct", "持有期盈亏", _pct(profit_pct), source="calculated"),
        _fact("stop.price", "当前止损价", decimal_string(stop), source="holding"),
        _fact("stop.distance_pct", "距止损", _pct(stop_distance_pct), source="calculated"),
        _fact("risk.holding_amount", "持仓止损风险", decimal_string(holding_risk), source="calculated"),
        _fact("risk.portfolio_status", "组合风险状态", budget["status"], source="risk_budget"),
        _fact("risk.portfolio_utilization_pct", "组合风险使用率", budget["utilization_pct"], source="risk_budget"),
        _fact("risk.portfolio_remaining", "组合剩余风险容量", budget["remaining_capacity"], source="risk_budget"),
        _fact("history.sample_count", "近期行情样本数", recent["sample_count"], source=recent.get("source") or "history"),
        _fact("history.return_5d_pct", "近期 5 日收益", metrics.return_5d_pct, source="calculated"),
        _fact("history.return_20d_pct", "近期 20 日收益", metrics.return_20d_pct, source="calculated"),
        _fact("history.return_60d_pct", "近期 60 日收益", metrics.return_60d_pct, source="calculated"),
        _fact("history.max_drawdown_pct", "近期最大回撤", metrics.max_drawdown_pct, source="calculated"),
        _fact("history.range_position_pct", "近期区间位置", metrics.range_position_pct, source="calculated"),
    ]
    return HoldingReviewSnapshot(
        holding_id=holding.id,
        holding_version=holding.version,
        code=holding.code,
        name=holding.name,
        asset_type=holding.type,
        status=holding.status,
        buy_date=holding.buy_date,
        holding_days=max(0, (local_now().date() - holding.buy_date).days),
        buy_price=decimal_string(buy),
        quantity=decimal_string(quantity),
        current_price=decimal_string(current),
        quote_state=holding.quote_state,
        quote_source=holding.quote_source,
        quoted_at=holding.quoted_at,
        profit_loss_pct=_pct(profit_pct),
        stop_loss_method=holding.stop_loss_method,
        stop_loss_price=decimal_string(stop),
        stop_loss_distance_pct=_pct(stop_distance_pct),
        triggered=holding.status == "triggered",
        history_points=[
            {"trade_date": item["trade_date"], "price": decimal_string(as_decimal(item["price"]))}
            for item in recent["points"]
        ],
        sample_count=recent["sample_count"],
        history_source=recent.get("source"),
        history_last_trade_date=recent["last_trade_date"],
        history_stale=recent["stale"],
        history_warning=recent.get("warning"),
        metrics=metrics,
        holding_risk_amount=decimal_string(holding_risk),
        position_limit_amount=decimal_string(position_limit),
        portfolio_status=budget["status"],
        portfolio_utilization_pct=budget["utilization_pct"],
        portfolio_remaining_capacity=budget["remaining_capacity"],
        portfolio_coverage_complete=(budget["covered_position_count"] == budget["open_position_count"]),
        facts=facts,
    )


def _validated_facts(snapshot: HoldingReviewSnapshot, ids: list[str]) -> list[AIReviewFact]:
    facts = {item.fact_id: item for item in snapshot.facts}
    if any(item not in facts for item in ids):
        raise AIReviewError("ai_response_invalid")
    return [facts[item] for item in ids]


def review_holding(
    db: Session,
    holding: Holding,
    settings: dict,
    provider: AIProvider,
    *,
    authority_stage: str,
    risk_plan_previews: bool,
) -> HoldingReviewResponse:
    if holding.status not in {"holding", "triggered"}:
        raise AIReviewError("holding_not_active")
    if holding.quote_state in {"unpriced", "stale", "error"} or as_decimal(holding.current_price) <= 0:
        raise AIReviewError("market_data_not_ready")
    try:
        recent = analysis_history(db, holding)
    except Exception as exc:
        from services.price_history import HistoryUnavailable

        if isinstance(exc, HistoryUnavailable):
            raise AIReviewError("history_data_unavailable") from exc
        raise
    snapshot = build_holding_review_snapshot(
        db, holding, recent, settings, authority_stage=authority_stage
    )
    output = provider.review(snapshot)
    reasons = [
        AIReviewReason(text=item.text, facts=_validated_facts(snapshot, item.fact_ids))
        for item in output.reasons
    ]
    scenarios = [
        AIReviewScenario(
            condition=item.condition,
            impact=item.impact,
            facts=_validated_facts(snapshot, item.fact_ids),
        )
        for item in output.risk_scenarios
    ]
    action = output.action
    confidence = output.confidence
    if holding.status == "triggered":
        action = "execute_existing_stop"
        confidence = "high"
        if not any(fact.fact_id == "holding.status" for reason in reasons for fact in reason.facts):
            reasons.insert(
                0,
                AIReviewReason(
                    text="权威持仓已进入止损触发状态。",
                    facts=_validated_facts(snapshot, ["holding.status"]),
                ),
            )
            reasons = reasons[:3]
    if snapshot.sample_count < 20 or snapshot.history_stale:
        confidence = "low"
        if action == "open_add_on_preview":
            action = "refresh_data"
    remaining = snapshot.portfolio_remaining_capacity
    add_on_allowed = (
        risk_plan_previews
        and snapshot.portfolio_coverage_complete
        and snapshot.portfolio_status == "available"
        and remaining is not None
        and as_decimal(remaining) > 0
        and holding.status == "holding"
        and snapshot.sample_count >= 20
        and not snapshot.history_stale
    )
    if action == "open_add_on_preview" and not add_on_allowed:
        action = "pause_add_on"
    limitations = list(dict.fromkeys([
        *output.limitations,
        "不包含新闻、财报、行业研究、券商可用资金和未来价格预测",
    ]))[:6]
    return HoldingReviewResponse(
        summary=output.summary,
        action=action,
        reasons=reasons,
        risk_scenarios=scenarios,
        limitations=limitations,
        confidence=confidence,
        can_open_add_on_preview=action == "open_add_on_preview" and add_on_allowed,
        current_quote_state=holding.quote_state,
        current_quote_at=holding.quoted_at,
        history_last_trade_date=snapshot.history_last_trade_date,
        generated_at=datetime.now(timezone.utc),
        model=provider.model,
    )


@contextmanager
def holding_review_lock(holding_id: int):
    with _locks_guard:
        lock = _holding_locks.setdefault(holding_id, Lock())
    if not lock.acquire(blocking=False):
        raise AIReviewError("ai_review_busy")
    try:
        yield
    finally:
        lock.release()
        with _locks_guard:
            if not lock.locked():
                _holding_locks.pop(holding_id, None)
