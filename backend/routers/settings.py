from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import ChannelMetadata, Setting
from schemas import ErrorResponse, SettingsResponse, SettingsUpdate
from services.supported_runtime import feature_not_supported


router = APIRouter(prefix="/settings", tags=["settings"])
DEFAULTS = {
    "poll_interval": 30, "monitor_interval": 5, "quote_retention_days": 90,
    "diagnostics_retention_days": 30, "import_max_bytes": 1048576,
    "import_max_rows": 1000, "portfolio_risk_limit_pct": Decimal("5"),
    "default_position_risk_limit_pct": Decimal("1"),
}
INTEGER_KEYS = {"poll_interval", "monitor_interval", "quote_retention_days", "diagnostics_retention_days", "import_max_bytes", "import_max_rows"}
DECIMAL_KEYS = {"portfolio_equity", "portfolio_risk_limit_pct", "default_position_risk_limit_pct"}
UNSUPPORTED_FIELDS = {
    "webhook_enabled", "webhook_target_url", "webhook_secret", "clear_webhook_secret",
    "webhook_payload_level", "quote_retention_days", "diagnostics_retention_days",
    "import_max_bytes", "import_max_rows",
}


def get_effective_settings(db: Session) -> dict:
    result = dict(DEFAULTS)
    rows = db.query(Setting).filter(Setting.key.in_(set(DEFAULTS) | {"portfolio_equity", "portfolio_equity_updated_at"})).all()
    for row in rows:
        if row.key in INTEGER_KEYS:
            result[row.key] = int(row.value)
        elif row.key in DECIMAL_KEYS:
            result[row.key] = Decimal(row.value)
        elif row.key == "portfolio_equity_updated_at":
            result[row.key] = datetime.fromisoformat(row.value)
    result.setdefault("portfolio_equity", None)
    result.setdefault("portfolio_equity_updated_at", None)
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


@router.put("", response_model=SettingsResponse, responses={409: {"model": ErrorResponse}})
def update_settings(data: SettingsUpdate, db: Session = Depends(get_db)):
    requested_unsupported = data.model_fields_set.intersection(UNSUPPORTED_FIELDS)
    if requested_unsupported:
        raise HTTPException(409, feature_not_supported("runtime_extension_settings"))
    old = get_effective_settings(db)
    incoming = data.model_dump(exclude_none=True, exclude={"webhook_secret", "clear_webhook_secret", "webhook_target_url"})
    prospective = {**old, **incoming}
    if prospective["default_position_risk_limit_pct"] > prospective["portfolio_risk_limit_pct"]:
        raise HTTPException(status_code=422, detail={
            "error_code": "position_risk_limit_exceeds_portfolio_limit",
            "field": "default_position_risk_limit_pct",
        })
    equity_changed = data.portfolio_equity is not None and data.portfolio_equity != old.get("portfolio_equity")
    if equity_changed:
        prospective["portfolio_equity_updated_at"] = datetime.now(timezone.utc)
    monitor_changed = prospective["monitor_interval"] != old["monitor_interval"]
    try:
        if monitor_changed:
            from scheduler import update_interval
            update_interval(prospective["monitor_interval"])
        for key, value in prospective.items():
            if key.startswith("webhook_") or value is None: continue
            row = db.query(Setting).filter(Setting.key == key).first()
            if row:
                row.value = value.isoformat() if isinstance(value, datetime) else str(value)
            else:
                db.add(Setting(key=key, value=value.isoformat() if isinstance(value, datetime) else str(value)))
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
