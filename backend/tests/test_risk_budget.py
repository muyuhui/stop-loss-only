from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from models import (
    Alert, DeliveryAttempt, ImportAudit, MigrationAuthority, Position,
    PositionEvent, PositionLot, StopRule,
)
from routers import positions, risk, settings
from schemas import RiskPlanRequest
from services.position_domain import activate_rule, create_position
from services.risk_budget import preview_position_plan, risk_budget_summary


def api():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    app = FastAPI()
    for item in (settings.router, positions.router, risk.router):
        app.include_router(item, prefix="/api")

    def override():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    return TestClient(app, raise_server_exceptions=False), factory


def enable_authority(factory):
    db = factory()
    state = db.get(MigrationAuthority, 1) or MigrationAuthority(id=1)
    state.stage = "new-authoritative"
    db.add(state)
    db.commit()
    db.close()


def configure(client, **overrides):
    payload = {
        "portfolio_equity": "100000.0000",
        "portfolio_risk_limit_pct": "5.00",
        "default_position_risk_limit_pct": "1.00",
    }
    payload.update(overrides)
    return client.put("/api/settings", json=payload)


def test_risk_settings_defaults_validation_persistence_and_partial_update():
    client, _ = api()
    defaults = client.get("/api/settings").json()
    assert defaults["portfolio_equity"] is None
    assert defaults["portfolio_risk_limit_pct"] == "5"
    assert defaults["default_position_risk_limit_pct"] == "1"
    assert defaults["portfolio_equity_updated_at"] is None

    saved = configure(client)
    assert saved.status_code == 200
    data = saved.json()
    assert data["portfolio_equity"] == "100000.0000"
    assert data["portfolio_equity_updated_at"]

    invalid = client.put("/api/settings", json={"default_position_risk_limit_pct": "6"})
    assert invalid.status_code == 422
    after_invalid = client.get("/api/settings").json()
    assert after_invalid["default_position_risk_limit_pct"] == "1.00"
    assert after_invalid["portfolio_equity"] == "100000.0000"

    partial = client.put("/api/settings", json={"poll_interval": 45})
    assert partial.status_code == 200
    assert partial.json()["portfolio_equity"] == "100000.0000"
    assert client.put("/api/settings", json={"portfolio_equity": "0"}).status_code == 422


def test_budget_coverage_is_quote_independent_and_incomplete_is_explicit():
    _, factory = api()
    db = factory()
    covered = create_position(db, code="000001", asset_type="stock", name="甲", quantity=100, unit_cost=10)
    activate_rule(db, covered, method="fixed", value=9)
    uncovered = create_position(db, code="000002", asset_type="stock", name="乙", quantity=100, unit_cost=5)
    db.flush()
    values = {
        "portfolio_equity": Decimal("100000"),
        "portfolio_risk_limit_pct": Decimal("5"),
        "default_position_risk_limit_pct": Decimal("1"),
        "portfolio_equity_updated_at": None,
    }
    result = risk_budget_summary(db, values)
    assert covered.current_price is None
    assert Decimal(result["used_risk_amount"]) == Decimal("100")
    assert result["status"] == "incomplete"
    assert result["covered_position_count"] == 1
    assert result["remaining_capacity"] is None
    assert result["uncovered_position_ids"] == [uncovered.id]


def test_position_plan_formula_board_lot_fund_precision_and_refusals():
    budget = {
        "status": "available", "reason_code": None, "portfolio_equity": "100000",
        "portfolio_equity_updated_at": None, "portfolio_risk_limit_pct": "5",
        "default_position_risk_limit_pct": "1", "portfolio_limit_amount": "5000",
        "used_risk_amount": "0", "remaining_capacity": "5000", "exceeded_amount": "0",
        "utilization_pct": "0", "open_position_count": 0, "covered_position_count": 0,
        "position_coverage_pct": None, "total_open_remaining_cost": "0",
        "covered_remaining_cost": "0", "cost_coverage_pct": None, "uncovered_position_ids": [],
    }
    stock = RiskPlanRequest(
        code="000001", name="甲", asset_type="stock", entry_price="20",
        stop_method="fixed", stop_value="18", entry_fees="5", estimated_exit_fees="5",
    )
    planned = preview_position_plan(stock, budget)
    assert planned["raw_quantity"] == "495"
    assert planned["recommended_quantity"] == "400"
    assert Decimal(planned["projected_loss_at_stop"]) == Decimal("810")
    assert Decimal(planned["required_capital"]) == Decimal("8005")

    fund = stock.model_copy(update={"asset_type": "fund"})
    fund_plan = preview_position_plan(fund, budget)
    assert fund_plan["recommended_quantity"] == "495.000000"

    incomplete = {**budget, "status": "incomplete", "remaining_capacity": None}
    assert preview_position_plan(stock, incomplete)["reason_code"] == "portfolio_risk_coverage_incomplete"
    breached = stock.model_copy(update={"stop_value": Decimal("20")})
    assert preview_position_plan(breached, budget)["reason_code"] == "non_positive_unit_risk"
    zero_lot = stock.model_copy(update={"entry_price": Decimal("20"), "stop_value": Decimal("10")})
    tiny_budget = {**budget, "portfolio_equity": "10000", "portfolio_limit_amount": "500", "remaining_capacity": "100"}
    assert preview_position_plan(zero_lot, tiny_budget)["reason_code"] == "quantity_below_minimum_increment"


def test_risk_api_states_authority_and_preview_no_writes():
    client, factory = api()
    assert client.get("/api/risk/budget").status_code == 409
    assert client.post("/api/risk/plans/preview", json={
        "code": "000001", "name": "甲", "asset_type": "stock", "entry_price": "20",
        "stop_method": "fixed", "stop_value": "18",
    }).status_code == 409

    enable_authority(factory)
    assert configure(client).status_code == 200
    budget = client.get("/api/risk/budget")
    assert budget.status_code == 200
    assert budget.json()["status"] == "available"

    tracked = (Position, PositionLot, StopRule, PositionEvent, Alert, ImportAudit, DeliveryAttempt)
    db = factory()
    before = [db.query(model).count() for model in tracked]
    db.close()
    preview = client.post("/api/risk/plans/preview", json={
        "code": "000001", "name": "甲", "asset_type": "stock", "entry_price": "20",
        "stop_method": "fixed", "stop_value": "18", "entry_fees": "5",
        "estimated_exit_fees": "5",
    })
    assert preview.status_code == 200
    assert preview.json()["recommended_quantity"] == "400"
    db = factory()
    after = [db.query(model).count() for model in tracked]
    db.close()
    assert after == before


def test_preview_handoff_requires_explicit_position_creation_and_refreshes_budget():
    client, factory = api()
    enable_authority(factory)
    configure(client)
    preview = client.post("/api/risk/plans/preview", json={
        "code": "000001", "name": "甲", "asset_type": "stock", "entry_price": "20",
        "stop_method": "fixed", "stop_value": "18", "entry_fees": "5",
        "estimated_exit_fees": "5",
    }).json()
    assert client.get("/api/positions").json()["items"] == []
    created = client.post("/api/positions", json={
        "code": preview["normalized_input"]["code"],
        "name": preview["normalized_input"]["name"],
        "asset_type": preview["normalized_input"]["asset_type"],
        "quantity": preview["recommended_quantity"],
        "unit_cost": preview["normalized_input"]["entry_price"],
        "fees": preview["entry_fees"],
        "stop_method": preview["normalized_input"]["stop_method"],
        "stop_value": preview["normalized_input"]["stop_value"],
    })
    assert created.status_code == 200
    assert created.json()["active_stop_rule"]["stop_price"] == "18.0000"
    refreshed = client.get("/api/risk/budget").json()
    assert Decimal(refreshed["used_risk_amount"]) == Decimal("805")


def test_percentage_handoff_keeps_the_preview_entry_reference_with_fees():
    client, factory = api()
    enable_authority(factory)
    configure(client)
    preview = client.post("/api/risk/plans/preview", json={
        "code": "000001", "name": "甲", "asset_type": "stock", "entry_price": "20",
        "stop_method": "percentage", "stop_value": "10", "entry_fees": "5",
        "estimated_exit_fees": "5",
    }).json()
    created = client.post("/api/positions", json={
        "code": "000001", "name": "甲", "asset_type": "stock",
        "quantity": preview["recommended_quantity"], "unit_cost": "20", "fees": "5",
        "stop_method": "percentage", "stop_value": "10",
    }).json()
    assert Decimal(created["active_stop_rule"]["stop_price"]) == Decimal(preview["initial_stop_price"])
