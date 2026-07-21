from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Setting
from schemas import SettingsResponse, SettingsUpdate


router = APIRouter(prefix="/settings", tags=["settings"])
DEFAULTS = {"poll_interval": 30, "monitor_interval": 5}


def get_effective_settings(db: Session) -> dict[str, int]:
    result = dict(DEFAULTS)
    for row in db.query(Setting).filter(Setting.key.in_(DEFAULTS)).all():
        result[row.key] = int(row.value)
    return result


@router.get("", response_model=SettingsResponse)
def get_settings(db: Session = Depends(get_db)):
    return get_effective_settings(db)


@router.put("", response_model=SettingsResponse)
def update_settings(data: SettingsUpdate, db: Session = Depends(get_db)):
    old = get_effective_settings(db)
    prospective = {**old, **data.model_dump(exclude_none=True)}
    monitor_changed = prospective["monitor_interval"] != old["monitor_interval"]
    try:
        if monitor_changed:
            from scheduler import update_interval
            update_interval(prospective["monitor_interval"])
        for key, value in prospective.items():
            row = db.query(Setting).filter(Setting.key == key).first()
            if row:
                row.value = str(value)
            else:
                db.add(Setting(key=key, value=str(value)))
        db.commit()
    except Exception as exc:
        db.rollback()
        if monitor_changed:
            try:
                from scheduler import update_interval
                update_interval(old["monitor_interval"])
            except Exception:
                pass
        raise HTTPException(status_code=500, detail="运行时设置应用失败") from exc
    return prospective
