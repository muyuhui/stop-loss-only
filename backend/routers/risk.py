from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from routers.settings import get_effective_settings
from schemas import RiskBudgetResponse, RiskPlanRequest, RiskPlanResponse
from services.risk_budget import preview_position_plan, risk_budget_summary
from services.shadow_projection import authority
from services.supported_runtime import capability_available


router = APIRouter(prefix="/risk", tags=["risk"])


def _require_capability(db: Session, capability: str) -> None:
    if not capability_available(authority(db).stage, capability):
        raise HTTPException(status_code=409, detail={"error_code": "new_authority_required"})


@router.get("/budget", response_model=RiskBudgetResponse)
def get_risk_budget(db: Session = Depends(get_db)):
    _require_capability(db, "risk_budget_reads")
    return risk_budget_summary(db, get_effective_settings(db))


@router.post("/plans/preview", response_model=RiskPlanResponse)
def preview_plan(data: RiskPlanRequest, db: Session = Depends(get_db)):
    _require_capability(db, "risk_plan_previews")
    budget = risk_budget_summary(db, get_effective_settings(db))
    return preview_position_plan(data, budget)
