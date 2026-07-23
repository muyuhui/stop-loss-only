from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models import Alert, ChannelMetadata, DeliveryAttempt
from services.delivery import deliver_due, enqueue_committed_alerts, normalize_target, payload_for


def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_delivery_is_idempotent_and_failure_does_not_change_alert():
    session = db(); alert = Alert(holding_name="A", holding_code="000001", lifecycle_key="a", idempotency_key="a", trigger_price=1, current_price=1)
    session.add_all([alert, ChannelMetadata(channel="webhook", enabled=True, target_url="https://example.com/hook")]); session.commit()
    assert enqueue_committed_alerts(session, [alert]) == 1
    assert enqueue_committed_alerts(session, [alert]) == 0
    assert deliver_due(session, sender=lambda *_: (_ for _ in ()).throw(TimeoutError())) == 0
    assert session.get(Alert, alert.id) is not None
    assert session.query(DeliveryAttempt).one().status == "pending"


def test_webhook_safety_and_minimal_payload(monkeypatch):
    monkeypatch.setattr("services.delivery.socket.getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 443))])
    with pytest.raises(ValueError, match="unsafe_webhook_target"): normalize_target("https://localhost/hook")
    alert = Alert(id=2, holding_name="A", holding_code="000001", trigger_price=1, current_price=1, created_at=datetime.now(timezone.utc))
    assert set(payload_for(alert, "minimal")) == {"event", "alert_id", "code", "created_at"}
