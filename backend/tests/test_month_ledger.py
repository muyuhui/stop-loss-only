from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config import config
from database import Base, get_db
from models import Alert, Holding, StopRuleHistory
from routers import dashboard


@pytest.fixture()
def api():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False)
    app = FastAPI()
    app.include_router(dashboard.router, prefix="/api")

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app, raise_server_exceptions=False), session_factory


def month_bounds():
    tz = ZoneInfo(config.timezone)
    now = datetime.now(tz)
    start = datetime.combine(now.date().replace(day=1), time.min, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
    next_start = datetime.combine((now.date().replace(day=1) + timedelta(days=32)).replace(day=1), time.min, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
    return start, next_start


def holding(**overrides):
    body = {
        "code": "000001", "name": "测试持仓", "type": "stock",
        "buy_price": Decimal("10"), "quantity": 100, "buy_date": date(2026, 1, 1),
        "current_price": Decimal("0"), "highest_price": Decimal("10"),
        "stop_loss_method": "fixed", "stop_loss_value": Decimal("9"), "stop_loss_price": Decimal("9"),
        "status": "holding", "close_price": None, "quote_state": "unpriced",
    }
    body.update(overrides)
    return Holding(**body)


def add(session, *rows):
    session.add_all(rows)
    session.commit()


def test_realized_attribution_by_close_month(api):
    client, session_factory = api
    start, _ = month_bounds()
    session = session_factory()
    add(session,
        holding(code="000001", name="本月平仓", status="closed", close_price=Decimal("9"),
                quote_state="live", current_price=Decimal("9"),
                created_at=start - timedelta(days=5), updated_at=start + timedelta(hours=2)),
        holding(code="000002", name="上月平仓", status="closed", close_price=Decimal("8"),
                quote_state="live", current_price=Decimal("8"),
                created_at=start - timedelta(days=40), updated_at=start - timedelta(days=1)),
    )
    summary = client.get("/api/dashboard").json()["month_summary"]
    assert summary["realized_profit_loss"] == -100.0
    assert summary["closed_count"] == 1
    assert summary["month"] == datetime.now(ZoneInfo(config.timezone)).strftime("%Y-%m")


def test_triggered_count_only_current_month(api):
    client, session_factory = api
    start, _ = month_bounds()
    session = session_factory()
    add(session,
        Alert(holding_name="本月触发", holding_code="000001", lifecycle_key="a", idempotency_key="a",
              trigger_price=Decimal("9"), current_price=Decimal("8.8"), disposition="triggered",
              created_at=start + timedelta(hours=2)),
        Alert(holding_name="上月触发", holding_code="000002", lifecycle_key="b", idempotency_key="b",
              trigger_price=Decimal("9"), current_price=Decimal("8.8"), disposition="triggered",
              created_at=start - timedelta(days=1)),
    )
    summary = client.get("/api/dashboard").json()["month_summary"]
    assert summary["triggered_count"] == 1


def test_stop_adjustment_direction_statistics(api):
    client, session_factory = api
    start, _ = month_bounds()
    session = session_factory()
    add(session,
        # A：上月基线 create（止损 9），本月 update 调低到 8 → 调整 1、调低 1
        StopRuleHistory(holding_id=1, code="000001", name="A", stop_loss_method="fixed",
                        stop_loss_value=Decimal("9"), stop_loss_price=Decimal("9"), source="create",
                        changed_at=start - timedelta(days=1)),
        StopRuleHistory(holding_id=1, code="000001", name="A", stop_loss_method="fixed",
                        stop_loss_value=Decimal("8"), stop_loss_price=Decimal("8"), source="update",
                        changed_at=start + timedelta(hours=2)),
        # B：本月 create 基线（止损 10，不计调整），update 调高到 11（调整 1、不调低），
        #    rearm 调低到 9（调整 1、调低 1）→ 合计调整 2、调低 1
        StopRuleHistory(holding_id=2, code="000002", name="B", stop_loss_method="fixed",
                        stop_loss_value=Decimal("10"), stop_loss_price=Decimal("10"), source="create",
                        changed_at=start + timedelta(hours=1)),
        StopRuleHistory(holding_id=2, code="000002", name="B", stop_loss_method="fixed",
                        stop_loss_value=Decimal("11"), stop_loss_price=Decimal("11"), source="update",
                        changed_at=start + timedelta(hours=3)),
        StopRuleHistory(holding_id=2, code="000002", name="B", stop_loss_method="fixed",
                        stop_loss_value=Decimal("9"), stop_loss_price=Decimal("9"), source="rearm",
                        changed_at=start + timedelta(hours=4)),
    )
    summary = client.get("/api/dashboard").json()["month_summary"]
    assert summary["stop_adjustment_count"] == 3
    assert summary["stop_lowered_count"] == 2


def test_largest_loss_from_priced_current_holdings(api):
    client, session_factory = api
    start, _ = month_bounds()
    session = session_factory()
    add(session,
        holding(code="000001", name="最大亏损", status="holding", quote_state="live",
                current_price=Decimal("8"), created_at=start - timedelta(days=3), updated_at=start - timedelta(days=3)),
        holding(code="000002", name="次大亏损", status="holding", quote_state="live",
                current_price=Decimal("9"), created_at=start - timedelta(days=2), updated_at=start - timedelta(days=2)),
        holding(code="000003", name="浮盈持仓", status="holding", quote_state="live",
                current_price=Decimal("12"), created_at=start - timedelta(days=1), updated_at=start - timedelta(days=1)),
    )
    largest = client.get("/api/dashboard").json()["month_summary"]["largest_loss"]
    assert largest == {"name": "最大亏损", "code": "000001", "profit_loss_amount": -200.0}


def test_largest_loss_null_when_no_loss(api):
    client, session_factory = api
    start, _ = month_bounds()
    session = session_factory()
    add(session,
        holding(code="000001", name="浮盈持仓", status="holding", quote_state="live",
                current_price=Decimal("12"), created_at=start - timedelta(days=1), updated_at=start - timedelta(days=1)),
    )
    summary = client.get("/api/dashboard").json()["month_summary"]
    assert summary["largest_loss"] is None


def test_largest_loss_null_without_valued_holdings(api):
    client, session_factory = api
    start, _ = month_bounds()
    session = session_factory()
    add(session, holding(code="000001", name="未定价持仓", status="holding", quote_state="unpriced",
                         current_price=Decimal("0"), created_at=start - timedelta(days=1), updated_at=start - timedelta(days=1)))
    summary = client.get("/api/dashboard").json()["month_summary"]
    assert summary["largest_loss"] is None


def test_empty_portfolio_returns_zero_summary(api):
    client, _ = api
    summary = client.get("/api/dashboard").json()["month_summary"]
    assert summary["realized_profit_loss"] == 0.0
    assert summary["closed_count"] == 0
    assert summary["triggered_count"] == 0
    assert summary["stop_adjustment_count"] == 0
    assert summary["stop_lowered_count"] == 0
    assert summary["largest_loss"] is None
    assert summary["month"] == datetime.now(ZoneInfo(config.timezone)).strftime("%Y-%m")
