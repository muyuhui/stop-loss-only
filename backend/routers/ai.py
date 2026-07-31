from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Holding
from routers.settings import get_effective_settings
from schemas import ErrorResponse, HoldingReviewResponse
from services.ai_provider import AIProviderError, get_ai_provider
from services.ai_review import AIReviewError, holding_review_lock, review_holding
from services.risk_budget import read_authority_stage
from services.supported_runtime import capability_available


router = APIRouter(prefix="/ai", tags=["ai"])
_STATUS = {
    "ai_not_configured": 409,
    "ai_review_busy": 409,
    "holding_not_active": 409,
    "market_data_not_ready": 409,
    "history_data_unavailable": 503,
    "ai_timeout": 504,
    "ai_rate_limited": 429,
    "ai_unavailable": 503,
    "ai_response_invalid": 502,
}
_MESSAGES = {
    "ai_not_configured": "请先在设置中配置 DeepSeek API Key",
    "ai_review_busy": "该持仓正在生成复盘，请稍后重试",
    "holding_not_active": "仅支持复盘活动持仓",
    "market_data_not_ready": "当前行情不可用于复盘，请先刷新行情",
    "history_data_unavailable": "近期历史行情暂时不可用",
    "ai_timeout": "DeepSeek 响应超时，请稍后重试",
    "ai_rate_limited": "DeepSeek 请求过于频繁，请稍后重试",
    "ai_unavailable": "DeepSeek 暂时不可用，请稍后重试",
    "ai_response_invalid": "DeepSeek 返回了无法验证的复盘结果，请重试",
}


def _raise(error_code: str):
    raise HTTPException(
        status_code=_STATUS.get(error_code, 503),
        detail={"message": _MESSAGES.get(error_code, "AI 复盘暂时不可用"), "error_code": error_code},
    )


def _require_ai(stage: str) -> None:
    if not capability_available(stage, "ai_holding_reviews"):
        raise HTTPException(
            status_code=409,
            detail={"message": "当前运行面不支持 AI 持仓复盘", "error_code": "feature_not_supported", "feature": "ai_holding_reviews"},
        )


@router.post(
    "/holdings/{holding_id}/review",
    response_model=HoldingReviewResponse,
    responses={409: {"model": ErrorResponse}, 429: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 503: {"model": ErrorResponse}, 504: {"model": ErrorResponse}},
)
def create_holding_review(holding_id: int, db: Session = Depends(get_db)):
    stage = read_authority_stage(db)
    _require_ai(stage)
    holding = db.get(Holding, holding_id)
    if holding is None:
        raise HTTPException(status_code=404, detail="holding_not_found")
    try:
        provider = get_ai_provider()
        with holding_review_lock(holding_id):
            return review_holding(
                db,
                holding,
                get_effective_settings(db),
                provider,
                authority_stage=stage,
                risk_plan_previews=capability_available(stage, "risk_plan_previews"),
            )
    except (AIReviewError, AIProviderError) as exc:
        _raise(exc.error_code)


@router.post(
    "/deepseek/test",
    responses={409: {"model": ErrorResponse}, 429: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 503: {"model": ErrorResponse}, 504: {"model": ErrorResponse}},
)
def test_deepseek_connection(db: Session = Depends(get_db)):
    _require_ai(read_authority_stage(db))
    try:
        return get_ai_provider().test_connection()
    except AIProviderError as exc:
        _raise(exc.error_code)
