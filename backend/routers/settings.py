from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from models import Setting

router = APIRouter(prefix="/settings", tags=["settings"])

_DEFAULTS = {"poll_interval": 30, "monitor_interval": 5}


class SettingsUpdate(BaseModel):
    poll_interval: int | None = None
    monitor_interval: int | None = None


def _get_settings(db: Session):
    result = dict(_DEFAULTS)
    for row in db.query(Setting).all():
        key = row.key
        val = row.value
        if key in ("poll_interval", "monitor_interval"):
            result[key] = int(val)
        else:
            result[key] = val
    return result


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    return _get_settings(db)


@router.put("")
def update_settings(data: SettingsUpdate, db: Session = Depends(get_db)):
    for key, val in {"poll_interval": data.poll_interval, "monitor_interval": data.monitor_interval}.items():
        if val is not None:
            row = db.query(Setting).filter(Setting.key == key).first()
            if row:
                row.value = str(val)
            else:
                db.add(Setting(key=key, value=str(val)))
    db.commit()
    if data.monitor_interval is not None:
        from scheduler import update_interval
        update_interval(data.monitor_interval)
    return _get_settings(db)
