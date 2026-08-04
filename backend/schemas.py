from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


HoldingStatus = Literal["holding", "triggered", "closed"]
QuoteStateName = Literal["unpriced", "live", "delayed", "close", "nav", "stale", "error"]


class HoldingCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=100)
    type: Literal["stock", "fund"]
    buy_price: float = Field(..., gt=0)
    quantity: int = Field(..., gt=0)
    buy_date: date
    stop_loss_method: Literal["fixed", "percentage", "trailing"]
    stop_loss_value: float = Field(..., gt=0)


class HoldingUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    stop_loss_method: Literal["fixed", "percentage", "trailing"] | None = None
    stop_loss_value: float | None = Field(None, gt=0)


class HoldingClose(BaseModel):
    close_price: float = Field(..., gt=0)


class HoldingResponse(BaseModel):
    id: int
    code: str
    name: str
    type: str
    buy_price: float
    quantity: int
    buy_date: date
    current_price: float | None
    highest_price: float
    stop_loss_method: str
    stop_loss_value: float
    stop_loss_price: float
    profit_loss_pct: float | None
    stop_loss_distance_pct: float | None
    status: HoldingStatus
    close_price: float | None = None
    quote_source: str | None = None
    quoted_at: datetime | None = None
    fetched_at: datetime | None = None
    quote_state: QuoteStateName = "unpriced"
    fresh_until: datetime | None = None
    is_actionable: bool = False
    quote_error_code: str | None = None
    last_cycle_id: str | None = None
    created_at: datetime
    updated_at: datetime


class HoldingPage(BaseModel):
    items: list[HoldingResponse]
    total: int
    page: int
    size: int


class HoldingHistoryPoint(BaseModel):
    trade_date: date
    price: float
    stop_loss_price: float
    triggered: bool


class HoldingHistoryResponse(BaseModel):
    holding_id: int
    range: Literal["1m", "3m", "6m", "1y"]
    buy_price: float
    stop_loss_method: str
    stop_loss_note: str
    source: str | None = None
    last_trade_date: date | None = None
    stale: bool
    warning: str | None = None
    points: list[HoldingHistoryPoint]


class StopHistoryItem(BaseModel):
    id: int
    stop_loss_method: str
    stop_loss_value: float
    stop_loss_price: float
    source: Literal["create", "update", "rearm"]
    changed_at: datetime


class StopHistoryResponse(BaseModel):
    items: list[StopHistoryItem]


class SettingsResponse(BaseModel):
    poll_interval: int
    monitor_interval: int
    webhook_enabled: bool = False
    webhook_target_configured: bool = False
    webhook_secret_configured: bool = False
    webhook_payload_level: Literal["minimal", "expanded"] = "minimal"
    quote_retention_days: int = 90
    diagnostics_retention_days: int = 30
    import_max_bytes: int = 1048576
    import_max_rows: int = 1000
    portfolio_equity: Decimal | None = None
    portfolio_risk_limit_pct: Decimal = Decimal("5")
    default_position_risk_limit_pct: Decimal = Decimal("1")
    portfolio_equity_updated_at: datetime | None = None
    deepseek_api_key_configured: bool = False


class SettingsUpdate(BaseModel):
    poll_interval: int | None = Field(None, ge=5, le=300)
    monitor_interval: int | None = Field(None, ge=1, le=60)
    webhook_enabled: bool | None = None
    webhook_target_url: str | None = Field(None, max_length=500)
    webhook_secret: str | None = Field(None, min_length=1, max_length=512)
    clear_webhook_secret: bool = False
    webhook_payload_level: Literal["minimal", "expanded"] | None = None
    quote_retention_days: int | None = Field(None, ge=1, le=3650)
    diagnostics_retention_days: int | None = Field(None, ge=1, le=3650)
    import_max_bytes: int | None = Field(None, ge=1024, le=10485760)
    import_max_rows: int | None = Field(None, ge=1, le=100000)
    portfolio_equity: Decimal | None = Field(None, gt=0)
    portfolio_risk_limit_pct: Decimal | None = Field(None, gt=0, le=100)
    default_position_risk_limit_pct: Decimal | None = Field(None, gt=0, le=100)
    deepseek_api_key: str | None = Field(None, min_length=16, max_length=512)
    clear_deepseek_api_key: bool = False


AIReviewAction = Literal[
    "execute_existing_stop",
    "pause_add_on",
    "continue_observing",
    "review_risk_exposure",
    "open_add_on_preview",
    "refresh_data",
]
AIReviewConfidence = Literal["high", "medium", "low"]


class AIReviewFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_id: str = Field(..., min_length=1, max_length=80, pattern=r"^[a-z0-9_.-]+$")
    label: str = Field(..., min_length=1, max_length=80)
    value: str | None = Field(None, max_length=120)
    as_of: str | None = Field(None, max_length=64)
    source: str = Field(..., min_length=1, max_length=80)


class AIReviewHistoryPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trade_date: date
    price: str


class AIReviewMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    return_5d_pct: str | None = None
    return_20d_pct: str | None = None
    return_60d_pct: str | None = None
    max_drawdown_pct: str | None = None
    range_position_pct: str | None = None


class HoldingReviewSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["1"] = "1"
    holding_id: int
    holding_version: int
    code: str
    name: str
    asset_type: Literal["stock", "fund"]
    status: HoldingStatus
    buy_date: date
    holding_days: int
    buy_price: str
    quantity: str
    current_price: str
    quote_state: QuoteStateName
    quote_source: str | None = None
    quoted_at: datetime | None = None
    profit_loss_pct: str
    stop_loss_method: Literal["fixed", "percentage", "trailing"]
    stop_loss_price: str
    stop_loss_distance_pct: str
    triggered: bool
    history_points: list[AIReviewHistoryPoint] = Field(..., min_length=1, max_length=60)
    sample_count: int = Field(..., ge=1, le=60)
    history_source: str | None = None
    history_last_trade_date: date
    history_stale: bool
    history_warning: str | None = Field(None, max_length=200)
    metrics: AIReviewMetrics
    holding_risk_amount: str | None = None
    position_limit_amount: str | None = None
    portfolio_status: str
    portfolio_utilization_pct: str | None = None
    portfolio_remaining_capacity: str | None = None
    portfolio_coverage_complete: bool
    facts: list[AIReviewFact] = Field(..., min_length=1, max_length=40)


class ProviderReviewReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1, max_length=240)
    fact_ids: list[str] = Field(..., min_length=1, max_length=5)


class ProviderRiskScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    condition: str = Field(..., min_length=1, max_length=180)
    impact: str = Field(..., min_length=1, max_length=240)
    fact_ids: list[str] = Field(default_factory=list, max_length=5)


class ProviderHoldingReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(..., min_length=1, max_length=240)
    action: AIReviewAction
    reasons: list[ProviderReviewReason] = Field(..., min_length=1, max_length=3)
    risk_scenarios: list[ProviderRiskScenario] = Field(default_factory=list, max_length=2)
    limitations: list[str] = Field(default_factory=list, max_length=6)
    confidence: AIReviewConfidence


class AIReviewReason(BaseModel):
    text: str
    facts: list[AIReviewFact]


class AIReviewScenario(BaseModel):
    condition: str
    impact: str
    facts: list[AIReviewFact]


class HoldingReviewResponse(BaseModel):
    summary: str
    action: AIReviewAction
    reasons: list[AIReviewReason]
    risk_scenarios: list[AIReviewScenario]
    limitations: list[str]
    confidence: AIReviewConfidence
    can_open_add_on_preview: bool
    current_quote_state: QuoteStateName
    current_quote_at: datetime | None = None
    history_last_trade_date: date
    generated_at: datetime
    provider: Literal["deepseek"] = "deepseek"
    model: str


StopMethodName = Literal["fixed", "percentage", "trailing"]


class RiskPlanRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=100)
    asset_type: Literal["stock", "fund"]
    entry_price: Decimal = Field(..., gt=0)
    stop_method: StopMethodName
    stop_value: Decimal = Field(..., gt=0)
    entry_fees: Decimal = Field(Decimal("0"), ge=0)
    estimated_exit_fees: Decimal = Field(Decimal("0"), ge=0)
    position_risk_limit_pct: Decimal | None = Field(None, gt=0, le=100)


class RiskAddOnPlanRequest(BaseModel):
    holding_id: int = Field(..., ge=1)
    planned_entry_price: Decimal = Field(..., gt=0)
    entry_fees: Decimal = Field(Decimal("0"), ge=0)
    estimated_exit_fees: Decimal = Field(Decimal("0"), ge=0)
    position_risk_limit_pct: Decimal | None = Field(None, gt=0, le=100)


class RiskBudgetResponse(BaseModel):
    status: Literal["unavailable", "incomplete", "available", "exhausted", "exceeded"]
    reason_code: str | None = None
    portfolio_equity: str | None = None
    portfolio_equity_updated_at: datetime | None = None
    portfolio_risk_limit_pct: str
    default_position_risk_limit_pct: str
    portfolio_limit_amount: str | None = None
    used_risk_amount: str
    remaining_capacity: str | None = None
    exceeded_amount: str
    utilization_pct: str | None = None
    open_position_count: int
    covered_position_count: int
    position_coverage_pct: str | None = None
    total_open_remaining_cost: str
    covered_remaining_cost: str
    cost_coverage_pct: str | None = None
    uncovered_position_ids: list[int] = Field(default_factory=list)


class RiskPlanResponse(BaseModel):
    plan_kind: Literal["new"] = "new"
    status: Literal["ready", "refused"]
    reason_code: str | None = None
    calculated_at: datetime
    normalized_input: dict
    budget: RiskBudgetResponse
    initial_stop_price: str | None = None
    effective_position_risk_limit_pct: str | None = None
    portfolio_limit_amount: str | None = None
    position_limit_amount: str | None = None
    remaining_portfolio_capacity: str | None = None
    allowed_plan_risk: str | None = None
    entry_fees: str
    estimated_exit_fees: str
    unit_price_risk: str | None = None
    raw_quantity: str | None = None
    quantity_increment: str
    recommended_quantity: str | None = None
    projected_loss_at_stop: str | None = None
    required_capital: str | None = None
    post_plan_portfolio_used_risk: str | None = None
    post_plan_portfolio_utilization_pct: str | None = None


class RiskHoldingSnapshot(BaseModel):
    id: int
    version: int
    code: str
    name: str
    asset_type: Literal["stock", "fund"]
    status: HoldingStatus
    quantity: str
    buy_price: str
    current_price: str | None = None
    quote_state: QuoteStateName
    is_actionable: bool
    stop_loss_price: str


class RiskAddOnPlanResponse(BaseModel):
    plan_kind: Literal["add_on"] = "add_on"
    status: Literal["ready", "refused"]
    reason_code: str | None = None
    calculated_at: datetime
    holding: RiskHoldingSnapshot
    budget: RiskBudgetResponse
    planned_entry_price: str
    existing_stop_price: str
    current_holding_risk: str | None = None
    effective_position_risk_limit_pct: str | None = None
    position_limit_amount: str | None = None
    remaining_position_capacity: str | None = None
    remaining_portfolio_capacity: str | None = None
    allowed_incremental_risk: str | None = None
    entry_fees: str
    estimated_exit_fees: str
    unit_price_risk: str | None = None
    raw_quantity: str | None = None
    quantity_increment: str
    recommended_quantity: str | None = None
    incremental_projected_loss: str | None = None
    required_capital: str | None = None
    post_plan_holding_risk: str | None = None
    post_plan_portfolio_used_risk: str | None = None
    post_plan_portfolio_utilization_pct: str | None = None


class PositionOpenRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=100)
    asset_type: Literal["stock", "fund"]
    quantity: float = Field(..., gt=0)
    unit_cost: float = Field(..., gt=0)
    fees: float = Field(0, ge=0)
    taxes: float = Field(0, ge=0)


class PositionLotRequest(BaseModel):
    quantity: float = Field(..., gt=0)
    unit_cost: float = Field(..., gt=0)
    fees: float = Field(0, ge=0)
    taxes: float = Field(0, ge=0)


class PositionCloseRequest(BaseModel):
    quantity: float = Field(..., gt=0)
    close_price: float = Field(..., gt=0)
    fees: float = Field(0, ge=0)
    taxes: float = Field(0, ge=0)


class PositionRiskRequest(BaseModel):
    expected_version: int = Field(..., ge=1)
    reason: str = Field(..., min_length=1, max_length=200)


class PositionRearmRequest(PositionRiskRequest):
    method: Literal["fixed", "percentage", "trailing"]
    value: float = Field(..., gt=0)


class ErrorDetail(BaseModel):
    message: str
    error_code: str
    feature: str | None = None
    cycle_id: str | None = None
    correlation_id: str | None = None


class ErrorResponse(BaseModel):
    detail: ErrorDetail


class RuntimeCapabilityMap(BaseModel):
    legacy_holding_writes: bool
    shadow_diagnostics: bool
    risk_budget_reads: bool
    risk_plan_previews: bool
    risk_covered_position_creation: bool
    position_lifecycle_writes: bool
    csv_portability: bool
    webhook_delivery: bool
    browser_notifications: bool
    ai_holding_reviews: bool


class RuntimeCapabilitiesResponse(BaseModel):
    authority_stage: str
    stable_runtime_supported: bool
    capabilities: RuntimeCapabilityMap


class QuoteResult(BaseModel):
    code: str
    asset_type: str
    current_price: float | None = None
    change_pct: float | None = None
    source: str
    quoted_at: datetime | None = None
    fetched_at: datetime | None = None
    fresh: bool
    state: QuoteStateName = "unpriced"
    fresh_until: datetime | None = None
    is_actionable: bool = False
    error_code: str | None = None
    error: str | None = None


class TriggerResult(BaseModel):
    id: int
    code: str
    name: str
    current_price: float
    stop_loss_price: float


class RefreshCycleResponse(BaseModel):
    cycle_id: str
    status: Literal["ok", "success", "partial", "skipped", "degraded", "failed"]
    market_open: bool
    calendar_degraded: bool
    requested: int
    processed: int
    triggered: list[TriggerResult]
    items: list[QuoteResult]
    error_code: str | None = None


class MonitoringCycleResponse(BaseModel):
    id: str
    kind: str
    scope: str
    status: Literal["success", "partial", "skipped", "degraded", "failed"]
    started_at: datetime
    finished_at: datetime | None = None
    requested_count: int
    success_count: int
    skipped_count: int
    failed_count: int
    triggered_count: int
    coverage_pct: float
    calendar_source: str | None = None
    degraded_reason: str | None = None
    error_code: str | None = None


class MonitoringCyclePage(BaseModel):
    items: list[MonitoringCycleResponse]
    total: int
    page: int
    size: int


class MonitoringStatusResponse(BaseModel):
    scheduler_running: bool
    next_run_at: datetime | None = None
    latest_cycle: MonitoringCycleResponse | None = None
    last_success_at: datetime | None = None
    freshness: Literal["healthy", "overdue", "market_closed", "no_success"]
    actionable_quote_coverage_pct: float | None = None
    valuation_quote_coverage_pct: float | None = None
    quote_coverage_pct: float | None = None
    overdue: bool
    reason_code: str | None = None
    market_session: Literal["pre_market", "open", "lunch", "closed"]


class AlertSummary(BaseModel):
    id: int
    holding_name: str
    holding_code: str
    trigger_price: float
    current_price: float
    created_at: datetime


class DashboardResponse(BaseModel):
    active_cost: float
    active_market_value: float
    unrealized_profit_loss: float
    unrealized_profit_loss_pct: float
    realized_profit_loss: float
    holding_count: int
    triggered_count: int
    closed_count: int
    active_alerts_count: int
    today_alert_count: int
    latest_alert: AlertSummary | None
    holdings: list[HoldingResponse]
    total_cost: float
    total_market_value: float
    total_profit_loss: float
    total_profit_loss_pct: float
    actionable_position_coverage_pct: float | None = None
    valuation_coverage_pct: float | None = None
