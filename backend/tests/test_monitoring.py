from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from migrations import backup_database, current_version, downgrade, restore_database, upgrade
from models import Alert, Holding
from services.market_clock import MARKET_TZ, is_in_trading_session, normalize_trade_date
from services.monitoring import run_monitoring_cycle


def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def holding(code="000001"):
    return Holding(
        code=code, name="测试", type="stock", buy_price=Decimal("10"), quantity=100,
        buy_date=date(2026, 1, 1), current_price=Decimal("10"), highest_price=Decimal("10"),
        stop_loss_method="fixed", stop_loss_value=Decimal("9"), stop_loss_price=Decimal("9"), status="holding",
    )


def quote(code="000001", price="8.8", fresh=True, error=None):
    now = datetime(2026, 7, 21, 10, 0, tzinfo=MARKET_TZ)
    return {
        "code": code, "asset_type": "stock", "current_price": Decimal(price) if error is None else None,
        "change_pct": 0, "source": "fixture", "quoted_at": now, "fetched_at": now,
        "fresh": fresh, "error": error,
    }


def test_market_clock_boundaries_and_formats():
    assert normalize_trade_date("20260721") == date(2026, 7, 21)
    assert normalize_trade_date("2026-07-21") == date(2026, 7, 21)
    assert is_in_trading_session(datetime(2026, 7, 21, 9, 30, tzinfo=MARKET_TZ))
    assert not is_in_trading_session(datetime(2026, 7, 21, 12, 0, tzinfo=MARKET_TZ))
    assert is_in_trading_session(datetime(2026, 7, 21, 15, 0, tzinfo=MARKET_TZ))


def test_one_quote_updates_duplicate_lots_and_triggers_once(monkeypatch):
    db = session()
    db.add_all([holding(), holding()])
    db.commit()
    monkeypatch.setattr("services.monitoring.is_market_open", lambda now=None: (True, False))
    result = run_monitoring_cycle(db, now=datetime(2026, 7, 21, 10, 0, tzinfo=MARKET_TZ), price_loader=lambda holdings, now=None: [quote()])
    assert result["processed"] == 2
    assert db.query(Holding).filter(Holding.status == "triggered").count() == 2
    assert db.query(Alert).count() == 2
    run_monitoring_cycle(db, price_loader=lambda holdings, now=None: [quote()])
    assert db.query(Alert).count() == 2


def test_stale_or_failed_quote_cannot_trigger(monkeypatch):
    db = session()
    db.add_all([holding("000001"), holding("000002")])
    db.commit()
    monkeypatch.setattr("services.monitoring.is_market_open", lambda now=None: (True, False))
    run_monitoring_cycle(db, price_loader=lambda holdings, now=None: [quote("000001", fresh=False), quote("000002", error="timeout")])
    assert db.query(Holding).filter(Holding.status == "holding").count() == 2
    assert db.query(Alert).count() == 0


def test_alert_snapshot_survives_holding_delete(monkeypatch):
    db = session()
    item = holding()
    db.add(item)
    db.commit()
    monkeypatch.setattr("services.monitoring.is_market_open", lambda now=None: (True, False))
    run_monitoring_cycle(db, price_loader=lambda holdings, now=None: [quote()])
    alert = db.query(Alert).one()
    db.delete(item)
    db.commit()
    assert alert.holding_name == "测试"
    assert alert.holding_code == "000001"


def test_legacy_migration_backup_and_restore(tmp_path: Path):
    database = tmp_path / "legacy.db"
    url = f"sqlite:///{database.as_posix()}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE holdings (id INTEGER PRIMARY KEY, code VARCHAR(20), name VARCHAR(100), type VARCHAR(10), buy_price FLOAT, quantity INTEGER, buy_date DATE, current_price FLOAT, highest_price FLOAT, stop_loss_method VARCHAR(20), stop_loss_value FLOAT, stop_loss_price FLOAT, status VARCHAR(20), close_price FLOAT, created_at DATETIME, updated_at DATETIME)"))
        conn.execute(text("CREATE TABLE alerts (id INTEGER PRIMARY KEY, holding_id INTEGER, trigger_price FLOAT, current_price FLOAT, read BOOLEAN, created_at DATETIME)"))
        conn.execute(text("INSERT INTO holdings VALUES (1,'000001','测试','stock',10,100,'2026-01-01',8.8,10,'fixed',9,9,'stopped_out',8.8,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        conn.execute(text("INSERT INTO alerts VALUES (1,1,9,8.8,0,CURRENT_TIMESTAMP)"))
    upgrade(engine, url, tmp_path / "backups")
    assert current_version(engine) == 2
    with engine.connect() as conn:
        assert conn.execute(text("SELECT status FROM holdings WHERE id=1")).scalar_one() == "closed"
        assert conn.execute(text("SELECT holding_name FROM alerts WHERE id=1")).scalar_one() == "测试"
    downgrade(engine)
    assert current_version(engine) == 0
    with engine.connect() as conn:
        assert conn.execute(text("SELECT status FROM holdings WHERE id=1")).scalar_one() == "stopped_out"
    upgrade(engine, url, tmp_path / "backups")
    backup, manifest = backup_database(url, tmp_path / "manual")
    restored = tmp_path / "restored.db"
    restore_database(backup, manifest, restored)
    assert restored.exists()
