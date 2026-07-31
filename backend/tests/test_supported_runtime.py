from __future__ import annotations

import sys
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import db_admin
import main
from database import Base, get_db
from models import ChannelMetadata, Holding, ImportAudit, MigrationAuthority, Position, Setting
from routers import dashboard, operations, positions, prices, runtime, settings
from services.monitoring import MonitoringDatabaseBusy
from services.shadow_projection import begin_shadow_read


@pytest.fixture()
def runtime_api():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    app = FastAPI()
    for router in (positions.router, prices.router, dashboard.router, settings.router, operations.router, runtime.router):
        app.include_router(router, prefix="/api")

    def override_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app, raise_server_exceptions=False), factory


@contextmanager
def _real_application(monkeypatch, stage: str):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    db = factory()
    db.add(MigrationAuthority(id=1, stage=stage, shadow_dirty=False))
    db.commit()
    db.close()
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "SessionLocal", factory)
    monkeypatch.setattr(main, "current_version", lambda _: main.LATEST_SCHEMA_VERSION)
    monkeypatch.setattr(main, "config", SimpleNamespace(scheduler_enabled=False))
    app = main.create_app()

    def override_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def _holding() -> Holding:
    return Holding(
        code="000001", name="权威持仓", type="stock", buy_price=Decimal("10"), quantity=100,
        buy_date=date(2026, 1, 1), current_price=Decimal("8"), highest_price=Decimal("10"),
        stop_loss_method="fixed", stop_loss_value=Decimal("9"), stop_loss_price=Decimal("9"),
        status="holding", quote_state="live", is_actionable=True,
    )


@pytest.mark.parametrize(
    (
        "stage",
        "stable",
        "legacy_writes",
        "shadow_diagnostics",
        "risk_reads",
        "risk_creation",
    ),
    [
        ("legacy", True, True, False, True, False),
        ("shadow-read", True, True, True, True, False),
        ("new-authoritative", False, False, False, True, True),
    ],
)
def test_runtime_capabilities_are_stage_aware(
    runtime_api,
    stage,
    stable,
    legacy_writes,
    shadow_diagnostics,
    risk_reads,
    risk_creation,
):
    client, factory = runtime_api
    db = factory()
    db.add(MigrationAuthority(id=1, stage=stage, shadow_dirty=False))
    db.commit()
    db.close()

    response = client.get("/api/runtime/capabilities")

    assert response.status_code == 200
    assert response.json() == {
        "authority_stage": stage,
        "stable_runtime_supported": stable,
        "capabilities": {
            "legacy_holding_writes": legacy_writes,
            "shadow_diagnostics": shadow_diagnostics,
            "risk_budget_reads": risk_reads,
            "risk_plan_previews": risk_reads,
            "risk_covered_position_creation": risk_creation,
            "position_lifecycle_writes": False,
            "csv_portability": False,
            "webhook_delivery": False,
            "ai_holding_reviews": stage in {"legacy", "shadow-read"},
        },
    }


def test_runtime_capability_discovery_does_not_create_authority_row(runtime_api):
    client, factory = runtime_api

    response = client.get("/api/runtime/capabilities")

    assert response.status_code == 200
    assert response.json()["authority_stage"] == "legacy"
    db = factory()
    assert db.query(MigrationAuthority).count() == 0
    db.close()


@pytest.mark.parametrize(
    ("stage", "ready_status", "stable"),
    [
        ("legacy", 200, True),
        ("shadow-read", 200, True),
        ("new-authoritative", 503, False),
    ],
)
def test_real_application_readiness_matches_runtime_capabilities(
    monkeypatch, stage, ready_status, stable
):
    with _real_application(monkeypatch, stage) as client:
        assert client.get("/api/health/live").status_code == 200
        ready = client.get("/api/health/ready")
        capabilities = client.get("/api/runtime/capabilities")

    assert ready.status_code == ready_status
    assert capabilities.status_code == 200
    assert capabilities.json()["authority_stage"] == stage
    assert capabilities.json()["stable_runtime_supported"] is stable
    if not stable:
        assert ready.json()["error_code"] == "new_authority_not_supported"


@pytest.mark.parametrize("stage", ["legacy", "shadow-read", "new-authoritative"])
def test_position_writes_are_rejected_in_every_runtime_stage(runtime_api, stage):
    client, factory = runtime_api
    db = factory()
    if stage == "shadow-read":
        db.add(_holding()); db.commit(); begin_shadow_read(db)
    else:
        db.add(MigrationAuthority(id=1, stage=stage, shadow_dirty=False))
    db.commit(); before = db.query(Position).count(); db.close()

    response = client.post("/api/positions", json={
        "code": "000002", "name": "不应创建", "asset_type": "stock", "quantity": 1, "unit_cost": 1,
    })

    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == "feature_not_supported"
    db = factory(); assert db.query(Position).count() == before; db.close()


def test_dashboard_keeps_holding_as_authority_when_shadow_exists(runtime_api):
    client, factory = runtime_api
    db = factory(); db.add(_holding()); db.commit(); begin_shadow_read(db); db.commit()
    assert db.query(Position).count() == 1
    db.query(Position).update({Position.remaining_cost: Decimal("999999")}); db.commit(); db.close()

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    assert response.json()["active_cost"] == 1000
    assert response.json()["holdings"][0]["name"] == "权威持仓"


def test_cutover_is_rejected_before_any_side_effect(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(sys, "argv", ["db_admin.py", "cutover"])
    monkeypatch.setattr(db_admin, "SessionLocal", lambda: calls.append("session"))
    monkeypatch.setattr(db_admin, "backup_database", lambda *args: calls.append("backup"))
    monkeypatch.setattr(db_admin, "rebuild_shadow", lambda *args: calls.append("rebuild"))

    with pytest.raises(SystemExit) as exc:
        db_admin.main()

    assert exc.value.code != 0
    assert calls == []
    assert "cutover_not_supported" in capsys.readouterr().err


@pytest.mark.parametrize("path", ["/api/prices/refresh", "/api/prices/000001/refresh"])
def test_refresh_busy_contract_is_shared(runtime_api, monkeypatch, path):
    client, _ = runtime_api
    monkeypatch.setattr("routers.prices.run_monitoring_cycle", lambda *args, **kwargs: {
        "cycle_id": "busy-cycle", "error_code": "refresh_busy",
    })
    response = client.post(path)
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "message": "已有刷新正在运行", "error_code": "refresh_busy", "cycle_id": "busy-cycle",
    }


@pytest.mark.parametrize("path", ["/api/prices/refresh", "/api/prices/000001/refresh"])
def test_refresh_database_and_unknown_errors_are_shared(runtime_api, monkeypatch, path):
    client, _ = runtime_api
    monkeypatch.setattr(
        "routers.prices.run_monitoring_cycle",
        lambda *args, **kwargs: (_ for _ in ()).throw(MonitoringDatabaseBusy("db-cycle")),
    )
    busy = client.post(path)
    assert busy.status_code == 503
    assert busy.json()["detail"]["error_code"] == "database_busy"
    monkeypatch.setattr(
        "routers.prices.run_monitoring_cycle",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("provider payload must stay private")),
    )
    failed = client.post(path)
    assert failed.status_code == 500
    assert failed.json()["detail"]["error_code"] == "refresh_failed"
    assert failed.json()["detail"]["correlation_id"]
    assert "provider payload" not in failed.text


def test_disabled_csv_and_webhook_calls_do_not_write(runtime_api):
    client, factory = runtime_api
    preview = client.post(
        "/api/operations/import/preview",
        content=b"account,code,name,asset_type,quantity,unit_cost,stop_method,stop_value\n",
        headers={"content-type": "application/octet-stream"},
    )
    export = client.get("/api/operations/export.csv")
    webhook = client.put("/api/settings", json={
        "webhook_enabled": True,
        "webhook_target_url": "https://example.com/hook",
        "webhook_secret": "must-not-be-stored",
    })
    for response in (preview, export, webhook):
        assert response.status_code == 409
        assert response.json()["detail"]["error_code"] == "feature_not_supported"

    db = factory()
    assert db.query(Position).count() == 0
    assert db.query(ImportAudit).count() == 0
    assert db.query(ChannelMetadata).count() == 0
    assert db.query(Setting).count() == 0
    db.close()
