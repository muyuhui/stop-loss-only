from datetime import date
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from models import (
    Alert, DeliveryAttempt, Holding, ImportAudit, MigrationAuthority, Position,
    PositionEvent, PositionLot, PositionQuote, PriceHistory, Setting, StopRule,
)
from routers import positions, risk, settings
from schemas import RiskAddOnPlanRequest, RiskPlanRequest
from services.position_domain import activate_rule, create_position
from services.risk_budget import (
    preview_add_on_plan,
    preview_position_plan,
    risk_budget_summary,
)
from services.shadow_projection import begin_shadow_read


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


def holding(
    *,
    code="000001",
    name="甲",
    asset_type="stock",
    buy_price="10",
    quantity=100,
    stop_price="9",
    status="holding",
    quote_state="unpriced",
    is_actionable=False,
):
    return Holding(
        code=code,
        name=name,
        type=asset_type,
        buy_price=Decimal(buy_price),
        quantity=quantity,
        buy_date=date(2026, 1, 1),
        current_price=Decimal("0"),
        highest_price=Decimal(buy_price),
        stop_loss_method="fixed",
        stop_loss_value=Decimal(stop_price),
        stop_loss_price=Decimal(stop_price),
        status=status,
        quote_state=quote_state,
        is_actionable=is_actionable,
    )


def risk_settings():
    return {
        "portfolio_equity": Decimal("100000"),
        "portfolio_risk_limit_pct": Decimal("5"),
        "default_position_risk_limit_pct": Decimal("1"),
        "portfolio_equity_updated_at": None,
    }


BUSINESS_MODELS = (
    Holding, Position, PositionLot, StopRule, PositionEvent, Alert, Setting,
    PriceHistory, PositionQuote, ImportAudit, DeliveryAttempt, MigrationAuthority,
)


def business_snapshot(db):
    snapshot = {}
    for model in BUSINESS_MODELS:
        columns = tuple(model.__table__.columns)
        rows = db.query(model).all()
        snapshot[model.__tablename__] = sorted(
            (tuple(getattr(row, column.key) for column in columns) for row in rows),
            key=repr,
        )
    return snapshot


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
    result = risk_budget_summary(db, risk_settings(), authority_stage="new-authoritative")
    assert covered.current_price is None
    assert Decimal(result["used_risk_amount"]) == Decimal("100")
    assert result["status"] == "incomplete"
    assert result["covered_position_count"] == 1
    assert result["remaining_capacity"] is None
    assert result["uncovered_position_ids"] == [uncovered.id]


def test_legacy_budget_uses_holdings_and_shadow_projection_is_not_double_counted():
    _, factory = api()
    db = factory()
    first = holding(quote_state="error", is_actionable=False)
    triggered = holding(
        code="000002",
        name="乙",
        buy_price="20",
        stop_price="18",
        status="triggered",
    )
    closed = holding(code="000003", name="丙", status="closed")
    closed.close_price = Decimal("9")
    db.add_all([first, triggered, closed])
    db.commit()

    legacy = risk_budget_summary(db, risk_settings(), authority_stage="legacy")
    assert Decimal(legacy["used_risk_amount"]) == Decimal("300")
    assert legacy["open_position_count"] == 2
    assert legacy["covered_position_count"] == 2
    assert Decimal(legacy["remaining_capacity"]) == Decimal("4700")

    begin_shadow_read(db)
    db.commit()
    assert db.query(Position).count() == 3
    db.query(Position).update({Position.remaining_cost: Decimal("999999")})
    db.commit()
    shadow = risk_budget_summary(db, risk_settings(), authority_stage="shadow-read")
    assert Decimal(shadow["used_risk_amount"]) == Decimal("300")
    assert shadow["open_position_count"] == 2

    first.status = "closed"
    db.commit()
    after_close = risk_budget_summary(db, risk_settings(), authority_stage="shadow-read")
    assert Decimal(after_close["used_risk_amount"]) == Decimal("200")
    assert after_close["open_position_count"] == 1
    db.close()


def test_legacy_budget_empty_and_incomplete_states_are_explicit():
    _, factory = api()
    db = factory()
    empty = risk_budget_summary(db, risk_settings(), authority_stage="legacy")
    assert empty["status"] == "available"
    assert empty["remaining_capacity"] == "5000"
    assert empty["position_coverage_pct"] is None

    row = holding(stop_price="0")
    db.add(row)
    db.flush()
    incomplete = risk_budget_summary(db, risk_settings(), authority_stage="legacy")
    assert incomplete["status"] == "incomplete"
    assert incomplete["remaining_capacity"] is None
    assert incomplete["uncovered_position_ids"] == [row.id]
    db.close()


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
    assert planned["plan_kind"] == "new"
    assert planned["raw_quantity"] == "495"
    assert planned["recommended_quantity"] == "400"
    assert Decimal(planned["projected_loss_at_stop"]) == Decimal("810")
    assert Decimal(planned["required_capital"]) == Decimal("8005")
    assert Decimal(planned["post_plan_portfolio_used_risk"]) == Decimal("810")
    assert Decimal(planned["post_plan_portfolio_utilization_pct"]) == Decimal("16.20")

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


def test_add_on_plan_uses_position_and_portfolio_capacity_and_preserves_stop():
    row = holding()
    row.id = 7
    row.version = 3
    budget = {
        "status": "available", "reason_code": None, "portfolio_equity": "100000",
        "portfolio_equity_updated_at": None, "portfolio_risk_limit_pct": "5",
        "default_position_risk_limit_pct": "1", "portfolio_limit_amount": "5000",
        "used_risk_amount": "100", "remaining_capacity": "800", "exceeded_amount": "0",
        "utilization_pct": "2", "open_position_count": 1, "covered_position_count": 1,
        "position_coverage_pct": "100", "total_open_remaining_cost": "1000",
        "covered_remaining_cost": "1000", "cost_coverage_pct": "100",
        "uncovered_position_ids": [],
    }
    request = RiskAddOnPlanRequest(
        holding_id=7,
        planned_entry_price="10",
        entry_fees="5",
        estimated_exit_fees="5",
    )
    result = preview_add_on_plan(request, budget, row)
    assert result["status"] == "ready"
    assert result["existing_stop_price"] == "9"
    assert result["current_holding_risk"] == "100"
    assert result["remaining_position_capacity"] == "900"
    assert result["allowed_incremental_risk"] == "800"
    assert result["raw_quantity"] == "790"
    assert result["recommended_quantity"] == "700"
    assert result["incremental_projected_loss"] == "710"
    assert result["post_plan_holding_risk"] == "810"
    assert result["post_plan_portfolio_used_risk"] == "810"
    assert result["post_plan_portfolio_utilization_pct"] == "16.20"
    assert result["required_capital"] == "7005"
    assert row.stop_loss_price == Decimal("9")

    position_limited = preview_add_on_plan(
        request.model_copy(update={"planned_entry_price": Decimal("11")}),
        {**budget, "remaining_capacity": "5000"},
        holding(buy_price="14", stop_price="10", quantity=100),
    )
    assert position_limited["remaining_position_capacity"] == "600"
    assert position_limited["allowed_incremental_risk"] == "600"


def test_add_on_plan_fund_rounding_and_refusal_reasons():
    fund = holding(asset_type="fund", quantity=100, buy_price="10", stop_price="9")
    fund.id = 8
    budget = {
        "status": "available", "reason_code": None, "portfolio_equity": "100000",
        "portfolio_equity_updated_at": None, "portfolio_risk_limit_pct": "5",
        "default_position_risk_limit_pct": "1", "portfolio_limit_amount": "5000",
        "used_risk_amount": "100", "remaining_capacity": "5000", "exceeded_amount": "0",
        "utilization_pct": "2", "open_position_count": 1, "covered_position_count": 1,
        "position_coverage_pct": "100", "total_open_remaining_cost": "1000",
        "covered_remaining_cost": "1000", "cost_coverage_pct": "100",
        "uncovered_position_ids": [],
    }
    request = RiskAddOnPlanRequest(holding_id=8, planned_entry_price="11")
    result = preview_add_on_plan(request, budget, fund)
    assert result["recommended_quantity"] == "450.000000"

    boundary = request.model_copy(update={"planned_entry_price": Decimal("9")})
    assert preview_add_on_plan(boundary, budget, fund)["reason_code"] == "entry_not_above_existing_stop"
    fund.status = "triggered"
    assert preview_add_on_plan(request, budget, fund)["reason_code"] == "holding_not_eligible"
    fund.status = "holding"
    fees = request.model_copy(update={"entry_fees": Decimal("1001")})
    assert preview_add_on_plan(fees, budget, fund)["reason_code"] == "fees_consume_risk_capacity"


def test_risk_api_states_authority_and_preview_no_writes():
    client, factory = api()
    unavailable = client.get("/api/risk/budget")
    assert unavailable.status_code == 200
    assert unavailable.json()["status"] == "unavailable"
    refused = client.post("/api/risk/plans/preview", json={
        "code": "000001", "name": "甲", "asset_type": "stock", "entry_price": "20",
        "stop_method": "fixed", "stop_value": "18",
    })
    assert refused.status_code == 200
    assert refused.json()["reason_code"] == "portfolio_equity_unset"
    db = factory()
    assert db.query(MigrationAuthority).count() == 0
    db.close()

    assert configure(client).status_code == 200
    budget = client.get("/api/risk/budget")
    assert budget.status_code == 200
    assert budget.json()["status"] == "available"

    db = factory()
    before = business_snapshot(db)
    db.close()
    preview = client.post("/api/risk/plans/preview", json={
        "code": "000001", "name": "甲", "asset_type": "stock", "entry_price": "20",
        "stop_method": "fixed", "stop_value": "18", "entry_fees": "5",
        "estimated_exit_fees": "5",
    })
    assert preview.status_code == 200
    assert preview.json()["recommended_quantity"] == "400"
    refused_after_configure = client.post("/api/risk/plans/preview", json={
        "code": "000001", "name": "甲", "asset_type": "stock", "entry_price": "20",
        "stop_method": "fixed", "stop_value": "20",
    })
    assert refused_after_configure.status_code == 200
    assert refused_after_configure.json()["reason_code"] == "non_positive_unit_risk"
    db = factory()
    after = business_snapshot(db)
    db.close()
    assert after == before


def test_add_on_api_is_read_only_for_ready_and_refused_plans():
    client, factory = api()
    configure(client)
    db = factory()
    row = holding(quote_state="live", is_actionable=True)
    row.current_price = Decimal("10")
    db.add(row)
    db.commit()
    holding_id = row.id
    before = business_snapshot(db)
    db.close()

    ready = client.post("/api/risk/plans/add-on-preview", json={
        "holding_id": holding_id,
        "planned_entry_price": "10",
        "entry_fees": "5",
        "estimated_exit_fees": "5",
    })
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["recommended_quantity"] == "800"
    assert ready.json()["holding"]["stop_loss_price"] == "9.0000"

    refused = client.post("/api/risk/plans/add-on-preview", json={
        "holding_id": holding_id, "planned_entry_price": "9",
    })
    assert refused.status_code == 200
    assert refused.json()["reason_code"] == "entry_not_above_existing_stop"
    assert client.post("/api/risk/plans/add-on-preview", json={
        "holding_id": 9999, "planned_entry_price": "10",
    }).status_code == 404

    db = factory()
    after = business_snapshot(db)
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
