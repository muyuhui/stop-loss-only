from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional


class HoldingCreate(BaseModel):
    code: str = Field(..., max_length=20)
    name: str = Field(..., max_length=100)
    type: str = Field(..., pattern="^(stock|fund)$")
    buy_price: float = Field(..., gt=0)
    quantity: int = Field(..., gt=0)
    buy_date: date
    stop_loss_method: str = Field(..., pattern="^(fixed|percentage|trailing)$")
    stop_loss_value: float = Field(..., gt=0)


class HoldingUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    stop_loss_method: Optional[str] = Field(None, pattern="^(fixed|percentage|trailing)$")
    stop_loss_value: Optional[float] = Field(None, gt=0)


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
    status: str
    close_price: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class HoldingListResponse(BaseModel):
    id: int
    code: str
    name: str
    type: str
    buy_price: float
    quantity: int
    buy_date: date
    current_price: float
    stop_loss_method: str
    stop_loss_value: float
    stop_loss_price: float
    profit_loss_pct: float
    stop_loss_distance_pct: float
    status: str

    class Config:
        from_attributes = True


class AlertResponse(BaseModel):
    id: int
    holding_id: int
    holding_name: str = ""
    holding_code: str = ""
    trigger_price: float
    current_price: float
    read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DashboardResponse(BaseModel):
    total_cost: float
    total_market_value: float
    total_profit_loss: float
    total_profit_loss_pct: float
    holding_count: int
    active_alerts_count: int
    holdings: list[HoldingListResponse]


class PriceResponse(BaseModel):
    code: str
    name: str
    current_price: float
    change_pct: float
    fetched_at: str
    error: Optional[str] = None
