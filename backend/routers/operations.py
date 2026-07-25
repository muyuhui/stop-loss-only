from pathlib import Path
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session
from config import config
from database import get_db
from migrations import backup_database
from services.supported_runtime import feature_not_supported
from schemas import ErrorResponse

router = APIRouter(prefix="/operations", tags=["operations"])

@router.post("/import/preview", responses={409: {"model": ErrorResponse}})
def import_preview(body: bytes = Body(..., media_type="application/octet-stream"), db: Session = Depends(get_db)):
    raise HTTPException(409, feature_not_supported("csv_import"))

@router.post("/import/{token}/commit", responses={409: {"model": ErrorResponse}})
def import_commit(token: str, db: Session = Depends(get_db)):
    raise HTTPException(409, feature_not_supported("csv_import"))

@router.get("/export.csv", responses={409: {"model": ErrorResponse}})
def export_csv(db: Session = Depends(get_db)):
    raise HTTPException(409, feature_not_supported("csv_export"))

@router.post("/backup")
def backup():
    folder = Path(__file__).resolve().parents[1] / "backups"
    backup, manifest = backup_database(config.database_url, folder)
    return {"backup": backup.name, "manifest": manifest.name, "schema_version": 7}

@router.get("/diagnostics")
def diagnostics(db: Session = Depends(get_db)):
    database = Path(config.database_url.removeprefix("sqlite:///"))
    return {"database_bytes": database.stat().st_size if database.exists() else 0, "database": "excluded", "secrets": "excluded", "provider_responses": "excluded"}
