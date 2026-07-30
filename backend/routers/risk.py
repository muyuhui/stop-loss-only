from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from routers.settings import get_effective_settings
from models import Holding
from schemas import (
    RiskAddOnPlanRequest,
    RiskAddOnPlanResponse,
    RiskBudgetResponse,
    RiskPlanRequest,
    RiskPlanResponse,
)
from services.risk_budget import (
    preview_add_on_plan,
    preview_position_plan,
    read_authority_stage,
    risk_budget_summary,
)
from services.supported_runtime import capability_available


router = APIRouter(prefix="/risk", tags=["risk"])


def _require_capability(db: Session, capability: str) -> None:
    if not capability_available(read_authority_stage(db), capability):
        raise HTTPException(status_code=409, detail={"error_code": "new_authority_required"})


@router.get("/budget", response_model=RiskBudgetResponse)
def get_risk_budget(db: Session = Depends(get_db)):
    _require_capability(db, "risk_budget_reads")
    return risk_budget_summary(
        db,
        get_effective_settings(db),
        authority_stage=read_authority_stage(db),
    )


@router.post("/plans/preview", response_model=RiskPlanResponse)
def preview_plan(data: RiskPlanRequest, db: Session = Depends(get_db)):
    _require_capability(db, "risk_plan_previews")
    budget = risk_budget_summary(
        db,
        get_effective_settings(db),
        authority_stage=read_authority_stage(db),
    )
    return preview_position_plan(data, budget)


@router.post("/plans/add-on-preview", response_model=RiskAddOnPlanResponse)
def preview_add_on(data: RiskAddOnPlanRequest, db: Session = Depends(get_db)):
    _require_capability(db, "risk_plan_previews")
    holding = db.get(Holding, data.holding_id)
    if holding is None:
        raise HTTPException(status_code=404, detail="holding_not_found")
    budget = risk_budget_summary(
        db,
        get_effective_settings(db),
        authority_stage=read_authority_stage(db),
    )
    return preview_add_on_plan(data, budget, holding)
