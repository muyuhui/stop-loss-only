from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from config import config
from database import get_db
from migrations import backup_database
from services.csv_portability import commit_preview, export_positions, preview_csv

router = APIRouter(prefix="/operations", tags=["operations"])

@router.post("/import/preview")
def import_preview(body: bytes, db: Session = Depends(get_db)):
    try: return preview_csv(body)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc

@router.post("/import/{token}/commit")
def import_commit(token: str, db: Session = Depends(get_db)):
    try: return {"positions": [row.id for row in commit_preview(db, token)]}
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc

@router.get("/export.csv", response_class=PlainTextResponse)
def export_csv(db: Session = Depends(get_db)):
    return PlainTextResponse(export_positions(db), media_type="text/csv")

@router.post("/backup")
def backup():
    folder = Path(__file__).resolve().parents[1] / "backups"
    backup, manifest = backup_database(config.database_url, folder)
    return {"backup": backup.name, "manifest": manifest.name, "schema_version": 7}

@router.get("/diagnostics")
def diagnostics(db: Session = Depends(get_db)):
    database = Path(config.database_url.removeprefix("sqlite:///"))
    return {"database_bytes": database.stat().st_size if database.exists() else 0, "database": "excluded", "secrets": "excluded", "provider_responses": "excluded"}
