from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from models import Alert, Holding, MonitoringCycle
from routers import alerts, dashboard, holdings, monitoring, prices, risk, settings


@pytest.fixture()
def api():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False)
    app = FastAPI()
    for router in (holdings.router, prices.router, alerts.router, dashboard.router, settings.router, monitoring.router, risk.router):
        app.include_router(router, prefix="/api")

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app, raise_server_exceptions=False), session_factory, app


def holding_body(**overrides):
    body = {
        "code": "000001", "name": "测试股票", "type": "stock", "buy_price": 10,
        "quantity": 100, "buy_date": "2026-01-01", "stop_loss_method": "fixed", "stop_loss_value": 9,
    }
    body.update(overrides)
    return body


def test_holding_contract_consistency_pagination_and_validation(api):
    client, _, _ = api
    created = client.post("/api/holdings", json=holding_body())
    assert created.status_code == 201
    item = created.json()
    assert item["current_price"] is None
    assert item["profit_loss_pct"] is None
    assert item["stop_loss_distance_pct"] is None
    assert item["quote_state"] == "unpriced" and item["is_actionable"] is False
    assert item["stop_loss_price"] == 9
    assert item["created_at"].endswith(("Z", "+00:00"))
    assert item["updated_at"].endswith(("Z", "+00:00"))
    detail = client.get(f"/api/holdings/{item['id']}").json()
    page = client.get("/api/holdings?page=1&size=1&status=holding").json()
    board = client.get("/api/dashboard").json()
    for field in ("stop_loss_price", "profit_loss_pct", "stop_loss_distance_pct"):
        assert detail[field] == page["items"][0][field] == board["holdings"][0][field]
    assert page | {"items": None} == {"items": None, "total": 1, "page": 1, "size": 1}
    assert client.get("/api/holdings?page=0").status_code == 422
    assert client.get("/api/holdings?status=unknown").status_code == 422


def test_update_is_atomic_and_delete_returns_204(api):
    client, _, _ = api
    item = client.post("/api/holdings", json=holding_body()).json()
    invalid = client.put(f"/api/holdings/{item['id']}", json={"name": "不应保存", "stop_loss_value": 11})
    assert invalid.status_code == 422
    assert client.get(f"/api/holdings/{item['id']}").json()["name"] == "测试股票"
    updated = client.put(f"/api/holdings/{item['id']}", json={"stop_loss_method": "percentage", "stop_loss_value": 10})
    assert updated.json()["stop_loss_price"] == 9
    deleted = client.delete(f"/api/holdings/{item['id']}")
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get(f"/api/holdings/{item['id']}").status_code == 404


def test_stop_rule_history_records_create_and_updates(api):
    client, _, _ = api
    created = client.post("/api/holdings", json=holding_body()).json()
    history = client.get(f"/api/holdings/{created['id']}/stop-history").json()
    assert len(history["items"]) == 1
    first = history["items"][0]
    assert first["source"] == "create"
    assert first["stop_loss_method"] == "fixed"
    assert first["stop_loss_value"] == 9
    assert first["stop_loss_price"] == 9
    assert first["changed_at"]

    updated = client.put(
        f"/api/holdings/{created['id']}",
        json={"stop_loss_method": "percentage", "stop_loss_value": 10},
    )
    assert updated.status_code == 200
    assert updated.json()["stop_loss_price"] == 9
    history = client.get(f"/api/holdings/{created['id']}/stop-history").json()
    assert len(history["items"]) == 2
    assert history["items"][0]["source"] == "update"
    assert history["items"][0]["stop_loss_method"] == "percentage"
    assert history["items"][0]["stop_loss_value"] == 10
    assert history["items"][0]["id"] > history["items"][1]["id"]
    assert history["items"][1]["source"] == "create"


def test_stop_rule_history_skips_noop_updates_and_survives_delete(api):
    client, _, _ = api
    item = client.post("/api/holdings", json=holding_body()).json()
    noop = client.put(f"/api/holdings/{item['id']}", json={"stop_loss_method": "fixed", "stop_loss_value": 9})
    assert noop.status_code == 200
    history = client.get(f"/api/holdings/{item['id']}/stop-history").json()
    assert len(history["items"]) == 1

    renamed = client.put(f"/api/holdings/{item['id']}", json={"name": "新名字"})
    assert renamed.status_code == 200
    history = client.get(f"/api/holdings/{item['id']}/stop-history").json()
    assert len(history["items"]) == 1

    assert client.delete(f"/api/holdings/{item['id']}").status_code == 204
    assert client.get(f"/api/holdings/{item['id']}").status_code == 404
    history = client.get(f"/api/holdings/{item['id']}/stop-history").json()
    assert len(history["items"]) == 1
    assert history["items"][0]["stop_loss_price"] == 9


def test_rearm_triggered_holding_restores_monitoring(api):
    client, factory, _ = api
    item = client.post("/api/holdings", json=holding_body()).json()
    db = factory()
    row = db.get(Holding, item["id"])
    row.status = "triggered"
    alert = Alert(
        holding_id=row.id, holding_name=row.name, holding_code=row.code, lifecycle_key="trigger-1",
        trigger_price=9, current_price=8.8, disposition="triggered",
    )
    db.add(alert)
    db.commit()
    db.close()

    rearmed = client.post(
        f"/api/holdings/{item['id']}/rearm",
        json={"stop_loss_method": "percentage", "stop_loss_value": 10},
    )
    assert rearmed.status_code == 200
    payload = rearmed.json()
    assert payload["status"] == "holding"
    assert payload["stop_loss_method"] == "percentage"
    assert payload["stop_loss_value"] == 10
    assert payload["stop_loss_price"] == 9

    db = factory()
    row = db.get(Holding, item["id"])
    assert row.status == "holding"
    assert row.trigger_sequence == 1
    assert row.version == 2
    assert [a.disposition for a in db.query(Alert).filter(Alert.holding_id == row.id).all()] == ["rearmed"]
    assert [a.read for a in db.query(Alert).filter(Alert.holding_id == row.id).all()] == [False]
    db.close()

    history = client.get(f"/api/holdings/{item['id']}/stop-history").json()
    assert history["items"][0]["source"] == "rearm"
    assert len(history["items"]) == 2


def test_rearm_validation_and_status_guards(api):
    client, factory, _ = api
    item = client.post("/api/holdings", json=holding_body()).json()
    # holding 状态拒绝
    assert client.post(f"/api/holdings/{item['id']}/rearm", json={"stop_loss_value": 8}).status_code == 400

    db = factory()
    db.get(Holding, item["id"]).status = "triggered"
    db.commit()
    db.close()
    # 校验失败 422 且无副作用
    bad = client.post(f"/api/holdings/{item['id']}/rearm", json={"stop_loss_value": 11})
    assert bad.status_code == 422
    detail = client.get(f"/api/holdings/{item['id']}").json()
    assert detail["status"] == "triggered"
    assert detail["stop_loss_value"] == 9
    # 平仓后拒绝
    assert client.post(f"/api/holdings/{item['id']}/close", json={"close_price": 8}).status_code == 200
    assert client.post(f"/api/holdings/{item['id']}/rearm", json={"stop_loss_value": 8}).status_code == 400


def test_lifecycle_close_and_alert_snapshot(api):
    client, factory, _ = api
    item = client.post("/api/holdings", json=holding_body()).json()
    db = factory()
    row = db.get(Holding, item["id"])
    row.status = "triggered"
    row.quoted_at = datetime(2026, 7, 22, 10, 4, 1)
    row.fetched_at = datetime(2026, 7, 22, 10, 4, 2)
    alert = Alert(
        holding_id=row.id, holding_name=row.name, holding_code=row.code, lifecycle_key="test",
        trigger_price=9, current_price=8.8, quoted_at=datetime(2026, 7, 22, 10, 4, 1),
        read=True,
    )
    db.add(alert)
    db.commit()
    db.close()
    detail = client.get(f"/api/holdings/{item['id']}").json()
    assert detail["quoted_at"].endswith("+08:00")
    assert detail["fetched_at"].endswith("+08:00")
    prices_page = client.get("/api/prices").json()
    assert prices_page["items"][0]["quoted_at"].endswith("+08:00")
    assert client.put(f"/api/holdings/{item['id']}", json={"name": "x"}).status_code == 400
    assert client.delete(f"/api/holdings/{item['id']}").status_code == 400
    closed = client.post(f"/api/holdings/{item['id']}/close", json={"close_price": 8.7})
    assert closed.json()["status"] == "closed"
    assert closed.json()["close_price"] == 8.7 and closed.json()["current_price"] is None
    assert client.delete(f"/api/holdings/{item['id']}").status_code == 204
    alerts_page = client.get("/api/alerts").json()
    assert alerts_page["items"][0]["quoted_at"].endswith("+08:00")
    assert alerts_page["items"][0]["created_at"].endswith("+00:00")
    assert alerts_page["items"][0]["holding_name"] == "测试股票"
    assert alerts_page["items"][0]["current_price"] == 8.8
    assert alerts_page["items"][0]["read"] is True
    assert alerts_page["items"][0]["disposition"] == "closed"


def test_alert_filters_search_before_pagination_and_normalize_legacy_disposition(api):
    client, factory, _ = api
    db = factory()
    db.add_all([
        Alert(
            holding_name="平安银行", holding_code="000001", lifecycle_key="alert-1",
            trigger_price=9, current_price=8.8, read=False, disposition=None,
        ),
        Alert(
            holding_name="平安基金", holding_code="000002", lifecycle_key="alert-2",
            trigger_price=2, current_price=1.9, read=True, disposition="closed",
        ),
        Alert(
            holding_name="招商银行", holding_code="600036", lifecycle_key="alert-3",
            trigger_price=30, current_price=29, read=False, disposition="triggered",
        ),
    ])
    db.commit()
    db.close()

    first_page = client.get("/api/alerts?search=平安&page=1&size=1").json()
    second_page = client.get("/api/alerts?search=平安&page=2&size=1").json()
    assert first_page["total"] == second_page["total"] == 2
    assert {first_page["items"][0]["holding_code"], second_page["items"][0]["holding_code"]} == {"000001", "000002"}
    assert client.get("/api/alerts?search=000002").json()["items"][0]["holding_name"] == "平安基金"

    read_page = client.get("/api/alerts?unread=false").json()
    assert read_page["total"] == 1 and read_page["items"][0]["read"] is True
    unresolved = client.get("/api/alerts?disposition=triggered").json()
    assert unresolved["total"] == 2
    assert {item["disposition"] for item in unresolved["items"]} == {"triggered"}
    assert client.get("/api/alerts?disposition=invalid").status_code == 422
    assert client.get(f"/api/alerts?search={'x' * 101}").status_code == 422


def test_dashboard_mixed_portfolio_and_today_alert(api):
    client, factory, _ = api
    first = client.post("/api/holdings", json=holding_body()).json()
    client.post(f"/api/holdings/{first['id']}/close", json={"close_price": 12})
    second = client.post("/api/holdings", json=holding_body(code="000002", name="活动持仓")).json()
    db = factory()
    current = db.get(Holding, second["id"])
    current.status = "triggered"
    db.add(Alert(holding_id=current.id, holding_name=current.name, holding_code=current.code, lifecycle_key="today", trigger_price=9, current_price=8.8))
    db.commit()
    db.close()
    data = client.get("/api/dashboard").json()
    assert data["active_cost"] == 1000
    assert data["realized_profit_loss"] == 200
    assert data["triggered_count"] == 1 and data["closed_count"] == 1
    assert data["today_alert_count"] == 1
    assert data["latest_alert"]["holding_code"] == "000002"
    assert data["latest_alert"]["created_at"].endswith(("Z", "+00:00"))
    assert len(data["holdings"]) == 1


def test_runtime_settings_defaults_validation_and_persistence(api, monkeypatch):
    client, _, _ = api
    calls = []
    monkeypatch.setattr("scheduler.update_interval", lambda value: calls.append(value))
    defaults = client.get("/api/settings").json()
    assert defaults["poll_interval"] == 30 and defaults["monitor_interval"] == 5
    assert defaults["webhook_enabled"] is False and defaults["webhook_secret_configured"] is False
    assert defaults["quote_retention_days"] == 90 and defaults["import_max_rows"] == 1000
    assert client.put("/api/settings", json={"poll_interval": 4}).status_code == 422
    response = client.put("/api/settings", json={"poll_interval": 45, "monitor_interval": 10})
    assert response.json()["poll_interval"] == 45 and response.json()["monitor_interval"] == 10
    assert calls == [10]
    assert client.get("/api/settings").json()["poll_interval"] == 45


def test_manual_refresh_partial_and_fatal_contract(api, monkeypatch):
    client, _, _ = api
    partial = {
        "cycle_id": "cycle-1", "status": "partial", "market_open": True, "calendar_degraded": False,
        "requested": 1, "processed": 0, "triggered": [],
        "items": [{"code": "000001", "asset_type": "stock", "current_price": None, "change_pct": None,
                   "source": "fixture", "quoted_at": None, "fetched_at": None, "fresh": False, "error": "timeout"}],
    }
    monkeypatch.setattr("routers.prices.run_monitoring_cycle", lambda db, scheduled=False: partial)
    response = client.post("/api/prices/refresh")
    assert response.status_code == 200 and response.json()["status"] == "partial"
    monkeypatch.setattr("routers.prices.run_monitoring_cycle", lambda db, scheduled=False: (_ for _ in ()).throw(RuntimeError("boom")))
    fatal = client.post("/api/prices/refresh")
    assert fatal.status_code == 500
    assert fatal.json()["detail"]["correlation_id"]


def test_holding_history_contract_ranges_and_errors(api, monkeypatch):
    client, _, _ = api
    item = client.post("/api/holdings", json=holding_body()).json()
    rows = [
        {"trade_date": date(2026, 7, 20), "price": Decimal("10.2"), "source": "fixture-history"},
        {"trade_date": date(2026, 7, 21), "price": Decimal("8.8"), "source": "fixture-history"},
    ]
    monkeypatch.setattr("services.price_history.local_now", lambda: datetime(2026, 7, 22, 12, 0))
    monkeypatch.setattr("services.price_history.fetch_price_history", lambda *args: rows)
    for range_name in ("1m", "3m", "6m", "1y"):
        response = client.get(f"/api/holdings/{item['id']}/history?range={range_name}")
        assert response.status_code == 200
        data = response.json()
        assert data["range"] == range_name
        assert data["points"] == sorted(data["points"], key=lambda point: point["trade_date"])
        assert data["stop_loss_note"]
    assert client.get(f"/api/holdings/{item['id']}/history?range=all").status_code == 422
    assert client.get("/api/holdings/999/history").status_code == 404


def test_openapi_contract_contains_models_and_statuses(api):
    _, _, app = api
    schema = app.openapi()
    assert "HoldingPage" in schema["components"]["schemas"]
    assert "DashboardResponse" in schema["components"]["schemas"]
    assert "RefreshCycleResponse" in schema["components"]["schemas"]
    assert "MonitoringStatusResponse" in schema["components"]["schemas"]
    assert "RiskPlanResponse" in schema["components"]["schemas"]
    assert "RiskAddOnPlanResponse" in schema["components"]["schemas"]
    assert "/api/monitoring/status" in schema["paths"]
    assert "/api/risk/plans/preview" in schema["paths"]
    assert "/api/risk/plans/add-on-preview" in schema["paths"]
    add_on_operation = schema["paths"]["/api/risk/plans/add-on-preview"]["post"]
    assert add_on_operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("/RiskAddOnPlanRequest")
    assert add_on_operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/RiskAddOnPlanResponse")
    assert "204" in schema["paths"]["/api/holdings/{holding_id}"]["delete"]["responses"]
    holding_schema = schema["components"]["schemas"]["HoldingResponse"]
    for field in ("profit_loss_pct", "stop_loss_distance_pct"):
        assert {item.get("type") for item in holding_schema["properties"][field]["anyOf"]} == {"number", "null"}


def test_monitoring_coverage_distinguishes_empty_denominator_from_measured_zero(api):
    client, _, _ = api
    empty = client.get("/api/monitoring/status").json()
    assert empty["actionable_quote_coverage_pct"] is None
    assert empty["valuation_quote_coverage_pct"] is None
    assert empty["quote_coverage_pct"] is None

    client.post("/api/holdings", json=holding_body())
    uncovered = client.get("/api/monitoring/status").json()
    assert uncovered["actionable_quote_coverage_pct"] == 0
    assert uncovered["valuation_quote_coverage_pct"] == 0
    assert uncovered["quote_coverage_pct"] == 0


def test_monitoring_status_and_paginated_cycles_are_actionable(api):
    client, factory, _ = api
    item = client.post("/api/holdings", json=holding_body()).json()
    db = factory()
    holding = db.get(Holding, item["id"])
    holding.quote_state = "live"
    holding.is_actionable = True
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(MonitoringCycle(
        id="diagnostic-cycle", kind="manual", scope="all", status="partial",
        started_at=now - timedelta(seconds=2), finished_at=now,
        requested_count=2, success_count=1, failed_count=1, skipped_count=0,
        triggered_count=0, coverage_pct=50, calendar_source="authoritative",
        error_code="instrument_failed",
    ))
    db.commit()
    db.close()
    status_response = client.get("/api/monitoring/status")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["latest_cycle"]["id"] == "diagnostic-cycle"
    assert status_data["quote_coverage_pct"] == 100
    assert status_data["overdue"] is True and status_data["reason_code"] == "no_successful_cycle"
    page = client.get("/api/monitoring/cycles?page=1&size=1&status=partial").json()
    assert page["total"] == 1 and page["items"][0]["error_code"] == "instrument_failed"
    assert client.get("/api/monitoring/cycles?status=unknown").status_code == 422
