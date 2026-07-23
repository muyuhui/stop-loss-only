from datetime import date
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sqlite3

from database import Base, get_db
from models import Holding, MigrationAuthority
from routers import positions
from services.shadow_projection import begin_shadow_read, rebuild_shadow, reconcile_shadow
from migrations import LATEST_SCHEMA_VERSION, current_version, upgrade


def _api():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    app = FastAPI(); app.include_router(positions.router, prefix="/api")
    def override():
        db = factory()
        try: yield db
        finally: db.close()
    app.dependency_overrides[get_db] = override
    return TestClient(app), factory


def test_shadow_read_projects_after_legacy_commit_and_rebuild_is_idempotent():
    client, factory = _api(); db = factory()
    db.add(Holding(code="000001", name="legacy", type="stock", buy_price=Decimal("10"), quantity=100, buy_date=date.today(), current_price=10, highest_price=10, stop_loss_method="fixed", stop_loss_value=9, stop_loss_price=9, status="holding")); db.commit()
    begin_shadow_read(db); db.commit()
    assert db.get(MigrationAuthority, 1).stage == "shadow-read"
    assert rebuild_shadow(db)["projected"] == 1 and reconcile_shadow(db)["matched"]
    db.commit(); db.close()
    listing = client.get("/api/positions")
    assert listing.status_code == 200 and listing.json()["items"][0]["remaining_quantity"] == "100.000000"
    assert client.post("/api/positions", json={"code": "000002", "name": "new", "asset_type": "stock", "quantity": 100, "unit_cost": 10}).status_code == 409


def test_history_is_bounded_and_preserves_event_timeline():
    client, factory = _api(); db = factory()
    db.add(Holding(code="000001", name="legacy", type="stock", buy_price=Decimal("10"), quantity=100, buy_date=date.today(), current_price=10, highest_price=10, stop_loss_method="fixed", stop_loss_value=9, stop_loss_price=9, status="holding")); db.commit()
    rebuild_shadow(db); db.commit(); db.close()
    response = client.get("/api/positions/1/history?size=1")
    assert response.status_code == 200 and response.json()["total"] >= 2 and len(response.json()["items"]) == 1


def test_upgrade_projects_a_representative_legacy_database(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE holdings (id INTEGER PRIMARY KEY, code VARCHAR(20) NOT NULL, name VARCHAR(100) NOT NULL, type VARCHAR(10) NOT NULL, buy_price NUMERIC NOT NULL, quantity INTEGER NOT NULL, buy_date DATE NOT NULL, current_price NUMERIC NOT NULL, highest_price NUMERIC NOT NULL, stop_loss_method VARCHAR(20) NOT NULL, stop_loss_value NUMERIC NOT NULL, stop_loss_price NUMERIC NOT NULL, status VARCHAR(20) NOT NULL, close_price NUMERIC, created_at DATETIME, updated_at DATETIME)")
        conn.execute("INSERT INTO holdings VALUES (1, '000001', 'legacy', 'stock', 10, 100, '2026-01-01', 10, 10, 'fixed', 9, 9, 'holding', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)")
    url = f"sqlite:///{path.as_posix()}"
    engine = create_engine(url)
    upgrade(engine, url, tmp_path)
    assert current_version(engine) == LATEST_SCHEMA_VERSION
    db = sessionmaker(bind=engine)()
    assert reconcile_shadow(db)["matched"] and db.get(MigrationAuthority, 1).shadow_dirty is False
