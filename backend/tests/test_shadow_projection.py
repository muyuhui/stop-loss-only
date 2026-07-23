from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models import CloseAllocation, Holding, MigrationAuthority, Position
from services.shadow_projection import cutover, rebuild_shadow, reconcile_shadow


def test_shadow_rebuild_reconciliation_and_cutover():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool); Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(Holding(code="000001", name="测试", type="stock", buy_price=Decimal("10"), quantity=100, buy_date=date.today(), current_price=0, highest_price=10, stop_loss_method="fixed", stop_loss_value=9, stop_loss_price=9, status="holding")); db.commit()
    assert rebuild_shadow(db)["projected"] == 1 and reconcile_shadow(db)["matched"]
    cutover(db)
    assert db.get(MigrationAuthority, 1).stage == "new-authoritative" and db.query(Position).count() == 1


def test_closed_legacy_holding_becomes_close_allocation():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool); Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(Holding(code="000002", name="关闭", type="stock", buy_price=Decimal("10"), quantity=100, buy_date=date.today(), current_price=9, highest_price=10, stop_loss_method="fixed", stop_loss_value=9, stop_loss_price=9, status="closed", close_price=Decimal("9"))); db.commit()
    rebuild_shadow(db); db.flush()
    assert db.query(Position).one().lifecycle_status == "closed" and db.query(CloseAllocation).count() == 1
