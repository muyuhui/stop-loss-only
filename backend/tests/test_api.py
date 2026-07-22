from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from models import Alert, Holding
from routers import alerts, dashboard, holdings, prices, settings


@pytest.fixture()
def api():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False)
    app = FastAPI()
    for router in (holdings.router, prices.router, alerts.router, dashboard.router, settings.router):
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


def test_lifecycle_close_and_alert_snapshot(api):
    client, factory, _ = api
    item = client.post("/api/holdings", json=holding_body()).json()
    db = factory()
    row = db.get(Holding, item["id"])
    row.status = "triggered"
    row.quoted_at = datetime(2026, 7, 22, 10, 4, 1)
    row.fetched_at = datetime(2026, 7, 22, 10, 4, 2)
    db.add(Alert(
        holding_id=row.id, holding_name=row.name, holding_code=row.code, lifecycle_key="test",
        trigger_price=9, current_price=8.8, quoted_at=datetime(2026, 7, 22, 10, 4, 1),
    ))
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
    assert client.delete(f"/api/holdings/{item['id']}").status_code == 204
    alerts_page = client.get("/api/alerts").json()
    assert alerts_page["items"][0]["quoted_at"].endswith("+08:00")
    assert alerts_page["items"][0]["created_at"].endswith("+00:00")
    assert alerts_page["items"][0]["holding_name"] == "测试股票"


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
    assert client.get("/api/settings").json() == {"poll_interval": 30, "monitor_interval": 5}
    assert client.put("/api/settings", json={"poll_interval": 4}).status_code == 422
    response = client.put("/api/settings", json={"poll_interval": 45, "monitor_interval": 10})
    assert response.json() == {"poll_interval": 45, "monitor_interval": 10}
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


def test_openapi_contract_contains_models_and_statuses(api):
    _, _, app = api
    schema = app.openapi()
    assert "HoldingPage" in schema["components"]["schemas"]
    assert "DashboardResponse" in schema["components"]["schemas"]
    assert "RefreshCycleResponse" in schema["components"]["schemas"]
    assert "204" in schema["paths"]["/api/holdings/{holding_id}"]["delete"]["responses"]
