from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models import CloseAllocation, PositionEvent
from services.position_domain import LifecycleStatus, RiskStatus, acknowledge_risk, activate_rule, close_position, create_position, decimal_quantity, portfolio_metrics, position_stop_metrics, rearm_position


def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_fund_fraction_and_stock_integrality():
    assert decimal_quantity("1.234567", "fund") == Decimal("1.234567")
    with pytest.raises(ValueError, match="integral"):
        decimal_quantity("1.5", "stock")


def test_fifo_partial_and_complete_close_accounting():
    db = db_session()
    position = create_position(db, code="510050", asset_type="fund", name="基金", quantity="10.5", unit_cost="2", fees="1")
    from services.position_domain import add_lot
    add_lot(db, position, quantity="5", unit_cost="3")
    db.flush()
    first = close_position(db, position, quantity="12", close_price="4", fees="1", taxes="1")
    db.flush()
    assert len(first) == 2 and first[0].quantity == Decimal("10.500000")
    assert position.lifecycle_status == LifecycleStatus.OPEN and position.remaining_quantity == Decimal("3.500000")
    second = close_position(db, position, quantity="3.5", close_price="4")
    db.flush()
    assert position.lifecycle_status == LifecycleStatus.CLOSED
    assert db.query(CloseAllocation).count() == 3
    assert db.query(PositionEvent).count() >= 4


def test_orthogonal_risk_and_coverage_formulas():
    db = db_session()
    first = create_position(db, code="000001", asset_type="stock", name="甲", quantity=100, unit_cost=10)
    second = create_position(db, code="000002", asset_type="stock", name="乙", quantity=100, unit_cost=5)
    first.current_price, first.is_actionable, first.risk_status = Decimal("11"), True, RiskStatus.TRIGGERED
    stats = portfolio_metrics([first, second])
    assert stats["actionable_position_coverage_pct"] == Decimal("50")
    assert stats["valuation_coverage_pct"] == Decimal("66.66666666666666666666666667")
    assert first.lifecycle_status == LifecycleStatus.OPEN and first.risk_status == RiskStatus.TRIGGERED
    with pytest.raises(ValueError):
        acknowledge_risk(db, first, expected_version=999, reason="已知悉")
    acknowledge_risk(db, first, expected_version=first.version, reason="已知悉")
    assert first.risk_status == RiskStatus.ACKNOWLEDGED


def test_stop_metrics_and_rearm_are_versioned():
    db = db_session()
    position = create_position(db, code="000001", asset_type="stock", name="甲", quantity=100, unit_cost=10)
    position.current_price, position.is_actionable, position.risk_status = Decimal("9.5"), True, RiskStatus.TRIGGERED
    rule = activate_rule(db, position, method="fixed", value=9)
    metrics = position_stop_metrics(position, rule, estimated_exit_cost=Decimal("5"))
    assert metrics["stop_risk_amount"] == Decimal("50") and metrics["estimated_loss_at_stop"] == Decimal("105")
    rearm_position(db, position, expected_version=position.version, method="fixed", value=8, reason="人工复核")
    assert position.risk_status == RiskStatus.NORMAL and position.trigger_sequence == 1
