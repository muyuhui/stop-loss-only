from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, Integer, Numeric, String, UniqueConstraint, func

from database import Base


PRICE_PRECISION = 18
PRICE_SCALE = 4


class Holding(Base):
    __tablename__ = "holdings"
    __table_args__ = (
        CheckConstraint("status IN ('holding', 'triggered', 'closed')", name="ck_holdings_status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(10), nullable=False)
    buy_price = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False)
    quantity = Column(Integer, nullable=False)
    buy_date = Column(Date, nullable=False)
    current_price = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False, default=0)
    highest_price = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False, default=0)
    stop_loss_method = Column(String(20), nullable=False)
    stop_loss_value = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False)
    stop_loss_price = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False, default=0)
    status = Column(String(20), nullable=False, default="holding", index=True)
    close_price = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=True)
    quote_source = Column(String(50), nullable=True)
    quoted_at = Column(DateTime(timezone=True), nullable=True)
    fetched_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("holding_id", "lifecycle_key", name="uq_alert_holding_lifecycle"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    holding_id = Column(Integer, nullable=True, index=True)
    holding_name = Column(String(100), nullable=False, default="")
    holding_code = Column(String(20), nullable=False, default="")
    lifecycle_key = Column(String(64), nullable=False)
    trigger_price = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False)
    current_price = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False)
    quote_source = Column(String(50), nullable=True)
    quoted_at = Column(DateTime(timezone=True), nullable=True)
    read = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(50), unique=True, nullable=False)
    value = Column(String(200), nullable=False)


class SchemaMigration(Base):
    __tablename__ = "schema_migrations"

    version = Column(Integer, primary_key=True)
    applied_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
