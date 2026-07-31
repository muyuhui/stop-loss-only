from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from migrations import backup_database
from models import Holding, PriceHistory, Setting
from observability import JsonFormatter
from routers import ai, operations, settings
from schemas import ProviderHoldingReview
from services.ai_provider import AIProviderError, DeepSeekProvider, FixtureDeepSeekProvider
from services.ai_review import (
    AIReviewError,
    build_holding_review_snapshot,
    review_holding,
    holding_review_lock,
)
from services.price_history import analysis_history
from services import secret_store


NOW = datetime(2026, 7, 30, 15, 0)


def make_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False)()


def make_holding(*, status: str = "holding", buy_date: date = date(2026, 7, 29)):
    return Holding(
        code="000001",
        name="测试持仓",
        type="stock",
        buy_price=Decimal("10"),
        quantity=100,
        buy_date=buy_date,
        current_price=Decimal("11"),
        highest_price=Decimal("12"),
        stop_loss_method="fixed",
        stop_loss_value=Decimal("9"),
        stop_loss_price=Decimal("9"),
        status=status,
        quote_state="live",
        quote_source="fixture",
        quoted_at=NOW,
        fetched_at=NOW,
        is_actionable=True,
    )


def risk_settings():
    return {
        "portfolio_equity": Decimal("100000"),
        "portfolio_risk_limit_pct": Decimal("5"),
        "default_position_risk_limit_pct": Decimal("1"),
        "portfolio_equity_updated_at": NOW,
    }


def history_rows(count: int = 60):
    start = NOW.date() - timedelta(days=count - 1)
    return [
        {
            "trade_date": start + timedelta(days=index),
            "price": Decimal("9") + Decimal(index) / Decimal("10"),
            "source": "fixture-history",
        }
        for index in range(count)
    ]


def test_analysis_history_is_independent_of_buy_date_and_caps_points(monkeypatch):
    db = make_db()
    holding = make_holding()
    db.add(holding)
    db.commit()
    monkeypatch.setattr("services.price_history.local_now", lambda: NOW)
    monkeypatch.setattr(
        "services.price_history.fetch_price_history", lambda *args: history_rows(75)
    )

    result = analysis_history(db, holding)

    assert result["sample_count"] == 60
    assert result["points"][0]["trade_date"] < holding.buy_date
    assert result["points"][-1]["trade_date"] == NOW.date()
    assert db.query(PriceHistory).count() == 75


def test_snapshot_metrics_are_deterministic_and_missing_periods_are_null(monkeypatch):
    db = make_db()
    holding = make_holding(buy_date=date(2026, 1, 1))
    db.add(holding)
    db.commit()
    monkeypatch.setattr("services.price_history.local_now", lambda: NOW)
    monkeypatch.setattr(
        "services.price_history.fetch_price_history", lambda *args: history_rows(25)
    )
    recent = analysis_history(db, holding)

    snapshot = build_holding_review_snapshot(
        db, holding, recent, risk_settings(), authority_stage="legacy"
    )

    assert snapshot.metrics.return_5d_pct is not None
    assert snapshot.metrics.return_20d_pct is not None
    assert snapshot.metrics.return_60d_pct is None
    assert snapshot.metrics.max_drawdown_pct is not None
    assert snapshot.metrics.range_position_pct is not None
    fact_ids = {item.fact_id for item in snapshot.facts}
    assert {"holding.status", "quote.current_price", "risk.portfolio_status"} <= fact_ids


def test_deepseek_provider_uses_current_official_json_contract():
    captured = {}

    def handler(request: httpx.Request):
        captured["authorization"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "deepseek-v4-flash",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "风险保持可控。",
                                    "action": "continue_observing",
                                    "reasons": [
                                        {
                                            "text": "当前状态正常。",
                                            "fact_ids": ["holding.status"],
                                        }
                                    ],
                                    "risk_scenarios": [],
                                    "limitations": ["不包含基本面"],
                                    "confidence": "medium",
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ],
            },
        )

    provider = DeepSeekProvider(
        "test-secret", transport=httpx.MockTransport(handler)
    )
    result = provider.review({"version": "1", "facts": []})

    assert result.action == "continue_observing"
    assert captured["authorization"] == "Bearer test-secret"
    assert captured["body"]["model"] == "deepseek-v4-flash"
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert captured["body"]["thinking"] == {"type": "disabled"}
    assert "json" in captured["body"]["messages"][0]["content"].lower()


@pytest.mark.parametrize(
    ("effect", "code"),
    [
        (httpx.ReadTimeout("slow"), "ai_timeout"),
        (httpx.Response(429, request=httpx.Request("POST", "https://api.deepseek.com")), "ai_rate_limited"),
        (httpx.Response(503, request=httpx.Request("POST", "https://api.deepseek.com")), "ai_unavailable"),
    ],
)
def test_deepseek_provider_maps_failures_without_leaking_payload(effect, code):
    def handler(request: httpx.Request):
        if isinstance(effect, Exception):
            raise effect
        return effect

    provider = DeepSeekProvider(
        "recognizable-secret", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(AIProviderError) as exc:
        provider.review({"version": "1", "facts": []})
    assert exc.value.error_code == code
    assert "recognizable-secret" not in str(exc.value)


def test_fixture_provider_supports_deterministic_success_and_failure_modes():
    success = FixtureDeepSeekProvider(mode="add-on").review(
        {"facts": [{"fact_id": "holding.status"}]}
    )
    assert success.action == "open_add_on_preview"

    with pytest.raises(AIProviderError) as exc:
        FixtureDeepSeekProvider(mode="timeout").review(
            {"facts": [{"fact_id": "holding.status"}]}
        )
    assert exc.value.error_code == "ai_timeout"


class FixtureProvider:
    model = "fixture-deepseek"

    def __init__(self, action="open_add_on_preview", fact_id="holding.status"):
        self.action = action
        self.fact_id = fact_id

    def review(self, snapshot):
        return ProviderHoldingReview.model_validate(
            {
                "summary": "基于近期行情的复盘。",
                "action": self.action,
                "reasons": [{"text": "引用权威事实。", "fact_ids": [self.fact_id]}],
                "risk_scenarios": [],
                "limitations": ["不包含新闻和财报"],
                "confidence": "high",
            }
        )

    def test_connection(self):
        return {"provider": "deepseek", "model": self.model, "status": "ok"}


def test_review_overrides_triggered_action_and_rejects_unknown_facts(monkeypatch):
    db = make_db()
    holding = make_holding(status="triggered", buy_date=date(2026, 1, 1))
    db.add(holding)
    db.commit()
    monkeypatch.setattr("services.price_history.local_now", lambda: NOW)
    monkeypatch.setattr(
        "services.price_history.fetch_price_history", lambda *args: history_rows(25)
    )

    result = review_holding(
        db,
        holding,
        risk_settings(),
        FixtureProvider(),
        authority_stage="legacy",
        risk_plan_previews=True,
    )
    assert result.action == "execute_existing_stop"
    assert result.can_open_add_on_preview is False

    with pytest.raises(AIReviewError) as exc:
        review_holding(
            db,
            holding,
            risk_settings(),
            FixtureProvider(fact_id="invented.fact"),
            authority_stage="legacy",
            risk_plan_previews=True,
        )
    assert exc.value.error_code == "ai_response_invalid"


def test_settings_store_deepseek_key_without_echo_or_database_write(monkeypatch):
    state = {"value": None}
    monkeypatch.setattr(settings, "get_secret", lambda name: state["value"])
    monkeypatch.setattr(settings, "set_secret", lambda name, value: state.update(value=value))
    monkeypatch.setattr(settings, "clear_secret", lambda name: state.update(value=None))
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    app = FastAPI()
    app.include_router(settings.router, prefix="/api")

    def override():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    client = TestClient(app, raise_server_exceptions=False)
    secret = "sk-recognizable-test-secret"

    saved = client.put("/api/settings", json={"deepseek_api_key": secret})
    assert saved.status_code == 200
    assert saved.json()["deepseek_api_key_configured"] is True
    assert secret not in saved.text
    db = factory()
    assert all(secret not in row.value for row in db.query(Setting).all())
    db.close()

    cleared = client.put("/api/settings", json={"clear_deepseek_api_key": True})
    assert cleared.status_code == 200
    assert cleared.json()["deepseek_api_key_configured"] is False


@pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI integration")
def test_machine_secret_store_round_trips_with_windows_dpapi(monkeypatch):
    test_root = Path(__file__).parent / f".secret-{uuid4().hex}"
    monkeypatch.setattr(secret_store, "config", SimpleNamespace(temp_dir=test_root))
    try:
        secret_store.set_secret("deepseek_api_key", "fixture-dpapi-round-trip")
        assert secret_store.get_secret("deepseek_api_key") == "fixture-dpapi-round-trip"
        secret_store.clear_secret("deepseek_api_key")
        assert secret_store.get_secret("deepseek_api_key") is None
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


def test_settings_preserve_existing_key_when_machine_store_is_unavailable(monkeypatch):
    state = {"value": "existing-key-that-must-survive"}
    monkeypatch.setattr(settings, "get_secret", lambda name: state["value"])
    monkeypatch.setattr(
        settings,
        "set_secret",
        lambda *args: (_ for _ in ()).throw(
            ValueError("machine_secret_storage_unavailable")
        ),
    )
    monkeypatch.setattr(settings, "clear_secret", lambda name: None)
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    app = FastAPI()
    app.include_router(settings.router, prefix="/api")

    def override():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    response = TestClient(app, raise_server_exceptions=False).put(
        "/api/settings", json={"deepseek_api_key": "replacement-key-long-enough"}
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == "machine_secret_storage_unavailable"
    assert state["value"] == "existing-key-that-must-survive"


def test_failed_connection_test_never_clears_saved_key(monkeypatch):
    state = {"value": "saved-key-that-must-survive"}

    class FailingProvider:
        def test_connection(self):
            raise AIProviderError("ai_rate_limited")

    client, _, _ = make_ai_api(monkeypatch, FailingProvider())
    monkeypatch.setattr(settings, "get_secret", lambda name: state["value"])
    monkeypatch.setattr(settings, "clear_secret", lambda name: state.update(value=None))

    response = client.post("/api/ai/deepseek/test")

    assert response.status_code == 429
    assert response.json()["detail"]["error_code"] == "ai_rate_limited"
    assert state["value"] == "saved-key-that-must-survive"


def make_ai_api(monkeypatch, provider=None):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    app = FastAPI()
    app.include_router(ai.router, prefix="/api")

    def override():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    fixture = provider or FixtureProvider(action="continue_observing")
    monkeypatch.setattr(ai, "get_ai_provider", lambda: fixture)
    monkeypatch.setattr("services.price_history.local_now", lambda: NOW)
    monkeypatch.setattr(
        "services.price_history.fetch_price_history", lambda *args: history_rows(25)
    )
    return TestClient(app, raise_server_exceptions=False), factory, fixture


def test_review_api_updates_only_history_cache(monkeypatch):
    client, factory, _ = make_ai_api(monkeypatch)
    db = factory()
    holding = make_holding(buy_date=date(2026, 1, 1))
    db.add(holding)
    db.commit()
    holding_id = holding.id
    before = {
        column.key: getattr(holding, column.key)
        for column in Holding.__table__.columns
    }
    db.close()

    response = client.post(f"/api/ai/holdings/{holding_id}/review")

    assert response.status_code == 200
    assert response.json()["action"] == "continue_observing"
    assert response.json()["history_last_trade_date"] == NOW.date().isoformat()
    db = factory()
    after_holding = db.get(Holding, holding_id)
    assert {
        column.key: getattr(after_holding, column.key)
        for column in Holding.__table__.columns
    } == before
    assert db.query(PriceHistory).count() == 25
    db.close()


@pytest.mark.parametrize(
    ("changes", "error_code"),
    [
        ({"status": "closed"}, "holding_not_active"),
        ({"quote_state": "unpriced", "current_price": Decimal("0")}, "market_data_not_ready"),
    ],
)
def test_review_api_rejects_ineligible_holding_before_provider(
    monkeypatch, changes, error_code
):
    calls = []

    class CountingProvider(FixtureProvider):
        def review(self, snapshot):
            calls.append(snapshot)
            return super().review(snapshot)

    client, factory, _ = make_ai_api(monkeypatch, CountingProvider())
    db = factory()
    holding = make_holding()
    for key, value in changes.items():
        setattr(holding, key, value)
    db.add(holding)
    db.commit()
    holding_id = holding.id
    db.close()

    response = client.post(f"/api/ai/holdings/{holding_id}/review")

    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == error_code
    assert calls == []


def test_review_api_rejects_duplicate_inflight_request_and_tests_connection(monkeypatch):
    client, factory, _ = make_ai_api(monkeypatch)
    db = factory()
    holding = make_holding()
    db.add(holding)
    db.commit()
    holding_id = holding.id
    db.close()

    with holding_review_lock(holding_id):
        busy = client.post(f"/api/ai/holdings/{holding_id}/review")
    assert busy.status_code == 409
    assert busy.json()["detail"]["error_code"] == "ai_review_busy"

    tested = client.post("/api/ai/deepseek/test")
    assert tested.status_code == 200
    assert tested.json() == {
        "provider": "deepseek",
        "model": "fixture-deepseek",
        "status": "ok",
    }


def _core_database_snapshot(db):
    return {
        name: [tuple(row) for row in db.execute(table.select()).all()]
        for name, table in sorted(Base.metadata.tables.items())
        if name != "price_history"
    }


def test_review_success_rejection_and_provider_failure_preserve_core_tables(monkeypatch):
    class FailingProvider(FixtureProvider):
        def review(self, snapshot):
            raise AIProviderError("ai_timeout")

    client, factory, _ = make_ai_api(monkeypatch)
    db = factory()
    active = make_holding(buy_date=date(2026, 1, 1))
    closed = make_holding(status="closed", buy_date=date(2026, 1, 1))
    db.add_all([active, closed, Setting(key="portfolio_equity", value="100000")])
    db.commit()
    active_id, closed_id = active.id, closed.id
    before = _core_database_snapshot(db)
    db.close()

    assert client.post(f"/api/ai/holdings/{active_id}/review").status_code == 200
    assert client.post(f"/api/ai/holdings/{closed_id}/review").status_code == 409
    monkeypatch.setattr(ai, "get_ai_provider", lambda: FailingProvider())
    assert client.post(f"/api/ai/holdings/{active_id}/review").status_code == 504

    db = factory()
    assert _core_database_snapshot(db) == before
    assert db.query(PriceHistory).count() == 25
    db.close()


def test_recognizable_key_is_absent_from_api_logs_diagnostics_and_backup(
    monkeypatch
):
    secret = "sk-recognizable-privacy-sentinel"
    state = {"value": None}
    monkeypatch.setattr(settings, "get_secret", lambda name: state["value"])
    monkeypatch.setattr(settings, "set_secret", lambda name, value: state.update(value=value))
    monkeypatch.setattr(settings, "clear_secret", lambda name: state.update(value=None))

    test_root = Path(__file__).parent / f".privacy-{uuid4().hex}"
    test_root.mkdir()
    try:
        database = test_root / "privacy.db"
        engine = create_engine(f"sqlite:///{database.as_posix()}")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, autoflush=False)
        app = FastAPI()
        app.include_router(settings.router, prefix="/api")
        app.include_router(operations.router, prefix="/api")

        def override():
            db = factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override
        client = TestClient(app, raise_server_exceptions=False)
        saved = client.put("/api/settings", json={"deepseek_api_key": secret})
        read_back = client.get("/api/settings")
        diagnostics = client.get("/api/operations/diagnostics")
        backup, manifest = backup_database(
            f"sqlite:///{database.as_posix()}", test_root / "backups"
        )

        record = logging.LogRecord("ai", logging.INFO, __file__, 1, "review_complete", (), None)
        record.authorization = f"Bearer {secret}"
        record.prompt = {"api_key": secret}
        rendered_log = JsonFormatter().format(record)
        public_bytes = "\n".join(
            [saved.text, read_back.text, diagnostics.text, rendered_log]
        ).encode("utf-8")
        backup_bytes = backup.read_bytes() + manifest.read_bytes()

        assert secret.encode("utf-8") not in public_bytes
        assert secret.encode("utf-8") not in database.read_bytes()
        assert secret.encode("utf-8") not in backup_bytes
        assert "Authorization" not in rendered_log
        assert "prompt" not in rendered_log
        engine.dispose()
    finally:
        shutil.rmtree(test_root, ignore_errors=True)
