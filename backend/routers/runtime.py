from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import MigrationAuthority
from schemas import RuntimeCapabilitiesResponse
from services.supported_runtime import runtime_policy


router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.get("/capabilities", response_model=RuntimeCapabilitiesResponse)
def get_runtime_capabilities(db: Session = Depends(get_db)):
    state = db.get(MigrationAuthority, 1)
    policy = runtime_policy(state.stage if state else "legacy")
    return {
        "authority_stage": policy.authority_stage,
        "stable_runtime_supported": policy.stable_runtime_supported,
        "capabilities": asdict(policy.capabilities),
    }
