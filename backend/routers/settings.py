from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import ChannelMetadata, Setting
from schemas import SettingsResponse, SettingsUpdate
from services.secret_store import clear_secret, set_secret
from services.delivery import normalize_target


router = APIRouter(prefix="/settings", tags=["settings"])
DEFAULTS = {"poll_interval": 30, "monitor_interval": 5, "quote_retention_days": 90, "diagnostics_retention_days": 30, "import_max_bytes": 1048576, "import_max_rows": 1000}


def get_effective_settings(db: Session) -> dict:
    result = dict(DEFAULTS)
    for row in db.query(Setting).filter(Setting.key.in_(DEFAULTS)).all():
        result[row.key] = int(row.value)
    channel = db.get(ChannelMetadata, "webhook")
    result.update({
        "webhook_enabled": bool(channel and channel.enabled),
        "webhook_target_configured": bool(channel and channel.target_url),
        "webhook_secret_configured": bool(channel and channel.secret_configured),
        "webhook_payload_level": channel.payload_level if channel else "minimal",
    })
    return result


@router.get("", response_model=SettingsResponse)
def get_settings(db: Session = Depends(get_db)):
    return get_effective_settings(db)


@router.put("", response_model=SettingsResponse)
def update_settings(data: SettingsUpdate, db: Session = Depends(get_db)):
    old = get_effective_settings(db)
    incoming = data.model_dump(exclude_none=True, exclude={"webhook_secret", "clear_webhook_secret", "webhook_target_url"})
    prospective = {**old, **incoming}
    monitor_changed = prospective["monitor_interval"] != old["monitor_interval"]
    try:
        if monitor_changed:
            from scheduler import update_interval
            update_interval(prospective["monitor_interval"])
        for key, value in prospective.items():
            if key.startswith("webhook_"): continue
            row = db.query(Setting).filter(Setting.key == key).first()
            if row:
                row.value = str(value)
            else:
                db.add(Setting(key=key, value=str(value)))
        channel = db.get(ChannelMetadata, "webhook") or ChannelMetadata(channel="webhook")
        if channel not in db: db.add(channel)
        if data.webhook_target_url is not None: channel.target_url = normalize_target(data.webhook_target_url) if data.webhook_target_url.strip() else None
        if data.webhook_enabled is not None: channel.enabled = data.webhook_enabled
        if data.webhook_payload_level is not None: channel.payload_level = data.webhook_payload_level
        if data.webhook_secret is not None:
            set_secret("webhook", data.webhook_secret)
            channel.secret_configured = True
        if data.clear_webhook_secret:
            clear_secret("webhook")
            channel.secret_configured = False
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
    return get_effective_settings(db)
