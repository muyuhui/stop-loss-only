import json
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models import Alert, Holding, MigrationAuthority, Setting
from services.desktop_notifier import (
    DesktopSummary,
    FixtureNotifier,
    desktop_notify_triggered,
    render_toast,
)
from services.market_clock import MARKET_TZ
from services.monitoring import run_monitoring_cycle


def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


class RecordingNotifier:
    def __init__(self):
        self.sent = []

    def send(self, summary, mode):
        self.sent.append((summary, mode))


def alert(name="平安银行", code="000001", price="8.8", stop="9"):
    return Alert(
        holding_id=1, holding_name=name, holding_code=code, lifecycle_key="k", idempotency_key="k",
        trigger_price=Decimal(stop), current_price=Decimal(price), disposition="triggered",
    )


def enable(db, *, mode="full", paused=False):
    db.add_all([
        Setting(key="desktop_notifications_enabled", value="True"),
        Setting(key="desktop_notification_mode", value=mode),
        Setting(key="desktop_notifications_paused", value="True" if paused else "False"),
    ])
    db.commit()


def holding(code="000001"):
    return Holding(
        code=code, name="测试", type="stock", buy_price=Decimal("10"), quantity=100,
        buy_date=date(2026, 1, 1), current_price=Decimal("10"), highest_price=Decimal("10"),
        stop_loss_method="fixed", stop_loss_value=Decimal("9"), stop_loss_price=Decimal("9"),
        status="holding", quote_state="live", is_actionable=True,
    )


def quote(code="000001", price="8.8"):
    return {
        "code": code, "asset_type": "stock", "current_price": Decimal(price),
        "change_pct": None, "source": "fixture", "quoted_at": None, "fetched_at": None,
        "fresh_until": None, "fresh": True, "state": "live", "is_actionable": True,
        "error": None, "error_code": None,
    }


def test_disabled_setting_does_not_send(monkeypatch):
    db = session()
    recorder = RecordingNotifier()
    monkeypatch.setattr("services.desktop_notifier.resolve_notifier", lambda: recorder)
    db.add(alert())
    db.commit()
    desktop_notify_triggered(db, [alert()])
    assert recorder.sent == []


def test_paused_setting_suppresses_send(monkeypatch):
    db = session()
    enable(db, paused=True)
    recorder = RecordingNotifier()
    monkeypatch.setattr("services.desktop_notifier.resolve_notifier", lambda: recorder)
    desktop_notify_triggered(db, [alert()])
    assert recorder.sent == []


def test_capability_gate_blocks_send(monkeypatch):
    db = session()
    enable(db)
    db.add(MigrationAuthority(id=1, stage="new-authoritative", shadow_dirty=False))
    db.commit()
    recorder = RecordingNotifier()
    monkeypatch.setattr("services.desktop_notifier.resolve_notifier", lambda: recorder)
    desktop_notify_triggered(db, [alert()])
    assert recorder.sent == []


def test_no_alerts_does_not_send(monkeypatch):
    db = session()
    enable(db)
    recorder = RecordingNotifier()
    monkeypatch.setattr("services.desktop_notifier.resolve_notifier", lambda: recorder)
    desktop_notify_triggered(db, [])
    assert recorder.sent == []


def test_full_mode_payload_contains_holding_info(monkeypatch):
    db = session()
    enable(db, mode="full")
    recorder = RecordingNotifier()
    monkeypatch.setattr("services.desktop_notifier.resolve_notifier", lambda: recorder)
    desktop_notify_triggered(db, [alert()])
    assert len(recorder.sent) == 1
    summary, mode = recorder.sent[0]
    assert mode == "full" and summary.count == 1
    assert summary.items[0]["name"] == "平安银行"
    assert summary.items[0]["code"] == "000001"
    assert summary.items[0]["current_price"] == 8.8
    assert summary.items[0]["trigger_price"] == 9.0
    title, body = render_toast(summary, mode)
    assert title == "止损触发提醒"
    assert "平安银行" in body and "000001" in body


def test_redacted_mode_payload_is_clean():
    summary = DesktopSummary(count=1, items=(
        {"name": "平安银行", "code": "000001", "current_price": 8.8, "trigger_price": 9.0},
    ))
    title, body = render_toast(summary, "redacted")
    assert title == "提醒"
    assert body == "有 1 笔触发待处理"
    for token in ("平安银行", "000001", "8.8", "9", "止损"):
        assert token not in body


def test_many_alerts_summarize_first_three():
    items = tuple({
        "name": f"持仓{i}", "code": f"00000{i}", "current_price": 8.8, "trigger_price": 9.0,
    } for i in range(1, 6))
    _, body = render_toast(DesktopSummary(count=5, items=items), "full")
    assert "等 5 笔触发止损" in body
    assert "持仓1" in body and "持仓3" in body
    assert "持仓4" not in body


def test_notifier_failure_is_isolated(monkeypatch):
    db = session()
    enable(db)
    def broken(summary, mode):
        raise RuntimeError("toast failed")
    monkeypatch.setattr("services.desktop_notifier.resolve_notifier", lambda: broken)
    desktop_notify_triggered(db, [alert()])  # 不应抛出


def test_fixture_notifier_writes_rendered_toast(monkeypatch, tmp_path):
    out = tmp_path / "notify.jsonl"
    monkeypatch.setattr(
        "services.desktop_notifier.config",
        SimpleNamespace(desktop_notify_fixture_enabled=True, desktop_notify_path=str(out)),
    )
    summary = DesktopSummary(count=1, items=(
        {"name": "平安银行", "code": "000001", "current_price": 8.8, "trigger_price": 9.0},
    ))
    FixtureNotifier().send(summary, "redacted")
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["mode"] == "redacted"
    assert record["title"] == "提醒"
    assert "待处理" in record["body"]
    for token in ("平安银行", "000001", "8.8", "止损"):
        assert token not in json.dumps(record, ensure_ascii=False)


def test_fixture_notifier_full_mode_contains_holding_info(monkeypatch, tmp_path):
    out = tmp_path / "notify.jsonl"
    monkeypatch.setattr(
        "services.desktop_notifier.config",
        SimpleNamespace(desktop_notify_fixture_enabled=True, desktop_notify_path=str(out)),
    )
    summary = DesktopSummary(count=1, items=(
        {"name": "平安银行", "code": "000001", "current_price": 8.8, "trigger_price": 9.0},
    ))
    FixtureNotifier().send(summary, "full")
    record = json.loads(out.read_text(encoding="utf-8").strip().splitlines()[0])
    assert record["title"] == "止损触发提醒"
    assert "平安银行" in record["body"] and "000001" in record["body"]


def test_monitoring_cycle_dispatches_desktop_notification(monkeypatch):
    db = session()
    enable(db, mode="full")
    db.add_all([holding(), holding("000002")])
    db.commit()
    recorder = RecordingNotifier()
    monkeypatch.setattr("services.desktop_notifier.resolve_notifier", lambda: recorder)
    monkeypatch.setattr("services.monitoring.is_market_open", lambda now=None: (True, False))

    result = run_monitoring_cycle(
        db, now=datetime(2026, 7, 21, 10, 0, tzinfo=MARKET_TZ),
        price_loader=lambda holdings, now=None: [quote(), quote("000002")],
    )
    assert result["processed"] == 2
    assert len(recorder.sent) == 1
    summary, mode = recorder.sent[0]
    assert mode == "full" and summary.count == 2
    assert {item["name"] for item in summary.items} == {"测试"}

    # 二次周期不产生新告警 → 不再发送
    run_monitoring_cycle(db, price_loader=lambda holdings, now=None: [quote(), quote("000002")])
    assert len(recorder.sent) == 1
