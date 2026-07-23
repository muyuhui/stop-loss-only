from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import socket
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from models import Alert, ChannelMetadata, DeliveryAttempt
from services.secret_store import get_secret


MAX_ATTEMPTS = 3


def normalize_target(raw: str) -> str:
    parsed = urlparse(raw.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("unsafe_webhook_target")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        if any(ipaddress.ip_address(item[4][0]).is_private or ipaddress.ip_address(item[4][0]).is_loopback or ipaddress.ip_address(item[4][0]).is_link_local or ipaddress.ip_address(item[4][0]).is_reserved for item in addresses):
            raise ValueError("unsafe_webhook_target")
    except socket.gaierror as exc:
        raise ValueError("webhook_target_unresolvable") from exc
    return parsed.geturl()


def payload_for(alert: Alert, level: str) -> dict:
    payload = {"event": "risk_triggered", "alert_id": alert.id, "code": alert.holding_code, "created_at": str(alert.created_at)}
    if level == "expanded": payload.update({"name": alert.holding_name, "trigger_price": str(alert.trigger_price), "current_price": str(alert.current_price)})
    return payload


def deliver_due(db: Session, *, sender=None) -> int:
    sender = sender or _send
    now = datetime.now(timezone.utc)
    attempts = db.query(DeliveryAttempt).filter(DeliveryAttempt.status == "pending", DeliveryAttempt.next_attempt_at <= now).all()
    delivered = 0
    for attempt in attempts:
        channel = db.get(ChannelMetadata, attempt.channel)
        alert = db.get(Alert, attempt.alert_id)
        try:
            if not channel or not channel.enabled or not alert: raise ValueError("delivery_disabled")
            sender(normalize_target(channel.target_url or ""), payload_for(alert, channel.payload_level), attempt.idempotency_key, get_secret("webhook"))
            attempt.status, attempt.attempts, attempt.next_attempt_at = "delivered", attempt.attempts + 1, None
            delivered += 1
        except Exception as exc:
            record_delivery_failure(db, attempt, str(exc) if str(exc) in {"unsafe_webhook_target", "webhook_target_unresolvable"} else "delivery_failed", commit=False)
    db.commit()
    return delivered


def _send(target: str, payload: dict, key: str, secret: str | None) -> None:
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(int(datetime.now(timezone.utc).timestamp()))
    signature = hmac.new((secret or "").encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    request = Request(target, data=body, method="POST", headers={"Content-Type": "application/json", "Idempotency-Key": key, "X-Webhook-Timestamp": timestamp, "X-Webhook-Signature": f"sha256={signature}"})
    with urlopen(request, timeout=3) as response:
        if response.status >= 300: raise ValueError("delivery_failed")


def enqueue_committed_alerts(db: Session, alerts: list[Alert]) -> int:
    """Create optional delivery work only after the caller committed alerts."""
    channel = db.get(ChannelMetadata, "webhook")
    if not channel or not channel.enabled or not channel.target_url:
        return 0
    created = 0
    for alert in alerts:
        key = f"webhook:{alert.idempotency_key}"
        if db.query(DeliveryAttempt).filter(DeliveryAttempt.idempotency_key == key).first():
            continue
        db.add(DeliveryAttempt(alert_id=alert.id, channel="webhook", idempotency_key=key, next_attempt_at=datetime.now(timezone.utc)))
        created += 1
    db.commit()
    return created


def record_delivery_failure(db: Session, attempt: DeliveryAttempt, code: str, *, commit=True) -> None:
    attempt.attempts += 1
    attempt.last_error_code = code
    attempt.status = "failed" if attempt.attempts >= MAX_ATTEMPTS else "pending"
    attempt.next_attempt_at = None if attempt.status == "failed" else datetime.now(timezone.utc) + timedelta(seconds=2 ** attempt.attempts)
    if commit: db.commit()
