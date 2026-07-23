from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import Alert, Holding, MonitoringCycle
from services.fixture_adapters import FixtureCalendar
from services.market_clock import MARKET_TZ
from services.monitoring import MonitoringDatabaseBusy, _refresh_lock, _trigger_key, run_monitoring_cycle


NOW = datetime(2026, 7, 23, 10, 0, tzinfo=MARKET_TZ)


def make_holding(code="000001"):
    return Holding(
        code=code, name=f"测试{code}", type="stock", buy_price=Decimal("10"), quantity=100,
        buy_date=date(2026, 1, 1), current_price=Decimal("0"), highest_price=Decimal("10"),
        stop_loss_method="fixed", stop_loss_value=Decimal("9"), stop_loss_price=Decimal("9"),
        status="holding", quote_state="unpriced", is_actionable=False,
    )


def quote(code="000001", price="8.8", *, state="live", actionable=True, error_code=None):
    return {
        "code": code, "asset_type": "stock", "current_price": Decimal(price) if price is not None else None,
        "change_pct": 0, "state": state, "source": "fixture", "quoted_at": NOW,
        "fetched_at": NOW, "fresh_until": NOW, "fresh": state not in {"error", "stale", "unpriced"},
        "is_actionable": actionable, "error_code": error_code,
        "error": "行情不可用" if error_code else None,
    }


def file_factory(tmp_path, *, timeout=1):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'monitoring.db').as_posix()}",
        connect_args={"check_same_thread": False, "timeout": timeout},
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, autoflush=False)


def test_concurrent_cycles_commit_only_one_trigger(tmp_path):
    _, factory = file_factory(tmp_path)
    db = factory()
    db.add(make_holding())
    db.commit()
    db.close()

    def run():
        session = factory()
        try:
            return run_monitoring_cycle(
                session, now=NOW, calendar=FixtureCalendar(), lock_timeout=2,
                price_loader=lambda holdings, now=None: [quote()],
            )
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: run(), range(2)))
    check = factory()
    assert check.query(Alert).count() == 1
    assert check.query(Holding).one().status == "triggered"
    assert sorted(len(result["triggered"]) for result in results) == [0, 1]
    assert all(item["cycle_id"] for item in results)
    check.close()


def test_partial_cycle_preserves_success_and_reports_committed_facts(tmp_path):
    _, factory = file_factory(tmp_path)
    db = factory()
    db.add_all([make_holding("000001"), make_holding("000002")])
    db.commit()
    result = run_monitoring_cycle(
        db, now=NOW, calendar=FixtureCalendar(),
        price_loader=lambda holdings, now=None: [
            quote("000001", "9.5"),
            quote("000002", None, state="error", actionable=False, error_code="provider_timeout"),
        ],
    )
    db.expire_all()
    good = db.query(Holding).filter(Holding.code == "000001").one()
    bad = db.query(Holding).filter(Holding.code == "000002").one()
    cycle = db.get(MonitoringCycle, result["cycle_id"])
    assert result["status"] == "partial" and result["processed"] == 1
    assert good.current_price == Decimal("9.5000") and good.quote_state == "live"
    assert bad.current_price == Decimal("0.0000") and bad.quote_state == "error"
    assert cycle.success_count == 1 and cycle.failed_count == 1 and float(cycle.coverage_pct) == 50


def test_unique_conflict_isolated_by_savepoint_and_does_not_report_trigger(tmp_path):
    _, factory = file_factory(tmp_path)
    db = factory()
    item = make_holding()
    db.add(item)
    db.commit()
    key = _trigger_key(item, 1)
    db.add(Alert(
        holding_id=item.id, holding_name=item.name, holding_code=item.code,
        lifecycle_key=key, idempotency_key=key, trigger_price=9, current_price=8.8,
    ))
    db.commit()
    result = run_monitoring_cycle(
        db, now=NOW, calendar=FixtureCalendar(),
        price_loader=lambda holdings, now=None: [quote()],
    )
    db.expire_all()
    assert result["triggered"] == []
    assert db.query(Alert).count() == 1
    assert db.get(Holding, item.id).status == "holding"
    assert db.get(MonitoringCycle, result["cycle_id"]).status == "failed"


def test_refresh_mutex_records_skipped_cycle(tmp_path):
    _, factory = file_factory(tmp_path)
    db = factory()
    assert _refresh_lock.acquire(timeout=0)
    try:
        result = run_monitoring_cycle(db, now=NOW, calendar=FixtureCalendar(), lock_timeout=0)
    finally:
        _refresh_lock.release()
    assert result["status"] == "skipped" and result["error_code"] == "refresh_busy"
    assert db.get(MonitoringCycle, result["cycle_id"]).status == "skipped"


def test_database_busy_has_stable_bounded_outcome(tmp_path):
    engine, factory = file_factory(tmp_path, timeout=0.05)
    lock = engine.connect()
    lock.exec_driver_sql("BEGIN EXCLUSIVE")
    db = factory()
    try:
        with pytest.raises(MonitoringDatabaseBusy) as captured:
            run_monitoring_cycle(db, now=NOW, calendar=FixtureCalendar(), lock_timeout=0)
        assert captured.value.error_code == "database_busy" and captured.value.cycle_id
    finally:
        db.close()
        lock.rollback()
        lock.close()


def test_scoped_refresh_only_touches_requested_holding(tmp_path):
    _, factory = file_factory(tmp_path)
    db = factory()
    first, second = make_holding("000001"), make_holding("000002")
    db.add_all([first, second])
    db.commit()
    result = run_monitoring_cycle(
        db, now=NOW, calendar=FixtureCalendar(), scope_holding_id=first.id,
        price_loader=lambda holdings, now=None: [quote("000001", "9.5")],
    )
    db.expire_all()
    assert result["requested"] == 1 and result["processed"] == 1
    assert db.get(Holding, first.id).quote_state == "live"
    assert db.get(Holding, second.id).quote_state == "unpriced"
