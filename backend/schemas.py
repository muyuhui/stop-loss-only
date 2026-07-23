from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


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
    profit_loss_pct: float
    stop_loss_distance_pct: float
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
    quote_coverage_pct: float
    overdue: bool
    reason_code: str | None = None


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
