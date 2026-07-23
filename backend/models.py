from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func

from database import Base


PRICE_PRECISION = 18
PRICE_SCALE = 4
QUANTITY_PRECISION = 18
QUANTITY_SCALE = 6


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
    quote_state = Column(String(20), nullable=False, default="unpriced", index=True)
    fresh_until = Column(DateTime(timezone=True), nullable=True)
    is_actionable = Column(Boolean, nullable=False, default=False)
    quote_error_code = Column(String(50), nullable=True)
    last_cycle_id = Column(String(32), nullable=True, index=True)
    version = Column(Integer, nullable=False, default=1)
    trigger_sequence = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PriceHistory(Base):
    __tablename__ = "price_history"
    __table_args__ = (
        UniqueConstraint("code", "asset_type", "trade_date", name="uq_price_history_asset_date"),
        Index("ix_price_history_asset_date", "code", "asset_type", "trade_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False)
    asset_type = Column(String(10), nullable=False)
    trade_date = Column(Date, nullable=False)
    price = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False)
    source = Column(String(50), nullable=False)
    fetched_at = Column(DateTime(timezone=True), nullable=False)


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
    idempotency_key = Column(String(64), nullable=True, unique=True)
    cycle_id = Column(String(32), nullable=True, index=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=True, index=True)
    trigger_event_id = Column(Integer, ForeignKey("position_events.id"), nullable=True)
    disposition = Column(String(20), nullable=True)
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


class MonitoringCycle(Base):
    __tablename__ = "monitoring_cycles"
    __table_args__ = (
        CheckConstraint("status IN ('success', 'partial', 'skipped', 'degraded', 'failed')", name="ck_monitoring_cycles_status"),
        Index("ix_monitoring_cycles_started_status", "started_at", "status"),
    )

    id = Column(String(32), primary_key=True)
    kind = Column(String(20), nullable=False)
    scope = Column(String(50), nullable=False, default="all")
    status = Column(String(20), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    requested_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    skipped_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    triggered_count = Column(Integer, nullable=False, default=0)
    coverage_pct = Column(Numeric(5, 2), nullable=False, default=0)
    calendar_source = Column(String(30), nullable=True)
    degraded_reason = Column(String(50), nullable=True)
    error_code = Column(String(50), nullable=True)


class MigrationAuthority(Base):
    __tablename__ = "migration_authority"
    id = Column(Integer, primary_key=True, default=1)
    stage = Column(String(20), nullable=False, default="legacy")
    shadow_dirty = Column(Boolean, nullable=False, default=False)
    readiness_reason = Column(String(80), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (UniqueConstraint("asset_type", "code", name="uq_instruments_type_code"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_type = Column(String(10), nullable=False)
    code = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    cost_basis_method = Column(String(10), nullable=False, default="fifo")
    is_default = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (
        CheckConstraint("lifecycle_status IN ('open', 'closed')", name="ck_positions_lifecycle"),
        CheckConstraint("risk_status IN ('normal', 'triggered', 'acknowledged')", name="ck_positions_risk"),
        Index("ix_positions_open_risk", "lifecycle_status", "risk_status"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    instrument_id = Column(Integer, ForeignKey("instruments.id"), nullable=False, index=True)
    lifecycle_status = Column(String(12), nullable=False, default="open")
    risk_status = Column(String(16), nullable=False, default="normal")
    remaining_quantity = Column(Numeric(QUANTITY_PRECISION, QUANTITY_SCALE), nullable=False, default=0)
    remaining_cost = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False, default=0)
    current_price = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=True)
    quote_state = Column(String(20), nullable=False, default="unpriced")
    is_actionable = Column(Boolean, nullable=False, default=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    trigger_sequence = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PositionLot(Base):
    __tablename__ = "position_lots"
    __table_args__ = (Index("ix_position_lots_fifo", "position_id", "opened_at", "id"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=False, index=True)
    quantity = Column(Numeric(QUANTITY_PRECISION, QUANTITY_SCALE), nullable=False)
    remaining_quantity = Column(Numeric(QUANTITY_PRECISION, QUANTITY_SCALE), nullable=False)
    unit_cost = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False)
    fees = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False, default=0)
    taxes = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False, default=0)
    opened_at = Column(DateTime(timezone=True), nullable=False)


class CloseAllocation(Base):
    __tablename__ = "close_allocations"
    __table_args__ = (Index("ix_close_allocations_position", "position_id", "closed_at"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=False, index=True)
    lot_id = Column(Integer, ForeignKey("position_lots.id"), nullable=False, index=True)
    quantity = Column(Numeric(QUANTITY_PRECISION, QUANTITY_SCALE), nullable=False)
    unit_cost = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False)
    close_price = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False)
    fees = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False, default=0)
    taxes = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False, default=0)
    proceeds = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False)
    realized_pnl = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=False)


class StopRule(Base):
    __tablename__ = "stop_rules"
    __table_args__ = (Index("ix_stop_rules_position_active", "position_id", "is_active"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    method = Column(String(20), nullable=False)
    value = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False)
    stop_price = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False)
    high_water_mark = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    activated_at = Column(DateTime(timezone=True), nullable=False)
    deactivated_at = Column(DateTime(timezone=True), nullable=True)


class PositionEvent(Base):
    __tablename__ = "position_events"
    __table_args__ = (Index("ix_position_events_timeline", "position_id", "occurred_at", "id"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=False, index=True)
    event_type = Column(String(30), nullable=False)
    schema_version = Column(Integer, nullable=False, default=1)
    payload = Column(String, nullable=False, default="{}")
    occurred_at = Column(DateTime(timezone=True), nullable=False)


class PositionQuote(Base):
    __tablename__ = "position_quotes"
    __table_args__ = (Index("ix_position_quotes_history", "position_id", "quoted_at", "id"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=False, index=True)
    price = Column(Numeric(PRICE_PRECISION, PRICE_SCALE), nullable=True)
    quote_state = Column(String(20), nullable=False)
    is_actionable = Column(Boolean, nullable=False, default=False)
    quoted_at = Column(DateTime(timezone=True), nullable=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False)


class DeliveryAttempt(Base):
    __tablename__ = "delivery_attempts"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_delivery_attempt_idempotency"), Index("ix_delivery_attempt_due", "status", "next_attempt_at"))
    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False, index=True)
    channel = Column(String(20), nullable=False)
    idempotency_key = Column(String(120), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    last_error_code = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ChannelMetadata(Base):
    __tablename__ = "channel_metadata"
    channel = Column(String(20), primary_key=True)
    enabled = Column(Boolean, nullable=False, default=False)
    target_url = Column(String(500), nullable=True)
    payload_level = Column(String(20), nullable=False, default="minimal")
    secret_configured = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ImportAudit(Base):
    __tablename__ = "import_audits"
    id = Column(Integer, primary_key=True, autoincrement=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    source_sha256 = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default="previewed")
    row_count = Column(Integer, nullable=False, default=0)
    valid_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    committed_at = Column(DateTime(timezone=True), nullable=True)


class RetentionState(Base):
    __tablename__ = "retention_state"
    key = Column(String(40), primary_key=True)
    cursor = Column(String(100), nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_deleted = Column(Integer, nullable=False, default=0)
