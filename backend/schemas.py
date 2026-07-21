from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


HoldingStatus = Literal["holding", "triggered", "closed"]


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
    current_price: float
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
    created_at: datetime
    updated_at: datetime


class HoldingPage(BaseModel):
    items: list[HoldingResponse]
    total: int
    page: int
    size: int


class SettingsResponse(BaseModel):
    poll_interval: int
    monitor_interval: int


class SettingsUpdate(BaseModel):
    poll_interval: int | None = Field(None, ge=5, le=300)
    monitor_interval: int | None = Field(None, ge=1, le=60)


class QuoteResult(BaseModel):
    code: str
    asset_type: str
    current_price: float | None = None
    change_pct: float | None = None
    source: str
    quoted_at: datetime | None = None
    fetched_at: datetime | None = None
    fresh: bool
    error: str | None = None


class TriggerResult(BaseModel):
    id: int
    code: str
    name: str
    current_price: float
    stop_loss_price: float


class RefreshCycleResponse(BaseModel):
    cycle_id: str
    status: Literal["ok", "partial", "skipped"]
    market_open: bool
    calendar_degraded: bool
    requested: int
    processed: int
    triggered: list[TriggerResult]
    items: list[QuoteResult]


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
