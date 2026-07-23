from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from models import Alert, CloseAllocation, Holding, Instrument, MigrationAuthority, Position, PositionEvent, PositionLot, PositionQuote, StopRule
from services.position_domain import LifecycleStatus, RiskStatus, activate_rule, close_position, create_position, event, utc_now


def authority(db: Session) -> MigrationAuthority:
    row = db.get(MigrationAuthority, 1)
    if row is None:
        row = MigrationAuthority(id=1, stage="legacy", shadow_dirty=False)
        db.add(row); db.flush()
    return row


def mark_shadow_dirty(db: Session, reason: str = "shadow_projection_failed") -> None:
    """Record a redacted recovery requirement without changing legacy facts."""
    state = authority(db)
    state.shadow_dirty = True
    state.readiness_reason = reason


def _legacy_status(position: Position) -> str:
    if position.lifecycle_status == "closed":
        return "closed"
    return "triggered" if position.risk_status == RiskStatus.TRIGGERED else "holding"


def rebuild_shadow(db: Session) -> dict:
    state = authority(db)
    if state.stage not in {"legacy", "shadow-read"}:
        raise ValueError("shadow_rebuild_not_allowed")
    db.query(PositionQuote).delete(); db.query(PositionEvent).delete(); db.query(CloseAllocation).delete(); db.query(StopRule).delete(); db.query(PositionLot).delete(); db.query(Position).delete()
    count = 0
    for legacy in db.query(Holding).order_by(Holding.id).all():
        position = create_position(db, code=legacy.code, asset_type=legacy.type, name=legacy.name, quantity=legacy.quantity, unit_cost=legacy.buy_price, opened_at=legacy.created_at)
        position.current_price = legacy.current_price if legacy.quote_state != "unpriced" else None
        position.quote_state, position.is_actionable = legacy.quote_state, legacy.is_actionable
        position.risk_status = RiskStatus.TRIGGERED if legacy.status == "triggered" else RiskStatus.NORMAL
        rule = activate_rule(db, position, method=legacy.stop_loss_method, value=legacy.stop_loss_value, reason="legacy_migration")
        rule.stop_price, rule.high_water_mark = legacy.stop_loss_price, legacy.highest_price
        if legacy.status == "closed":
            rule.is_active, rule.deactivated_at = False, legacy.updated_at or utc_now()
        if legacy.quote_state != "unpriced":
            db.add(PositionQuote(
                position_id=position.id, price=legacy.current_price, quote_state=legacy.quote_state,
                is_actionable=legacy.is_actionable, quoted_at=legacy.quoted_at,
                recorded_at=legacy.fetched_at or legacy.updated_at or utc_now(),
            ))
        if legacy.status == "closed":
            close_position(db, position, quantity=position.remaining_quantity, close_price=legacy.close_price or legacy.current_price, closed_at=legacy.updated_at or utc_now())
            event(db, position, "legacy_closed", {"close_price": str(legacy.close_price)}, clock=lambda: legacy.updated_at or utc_now())
        else:
            event(db, position, "legacy_triggered" if legacy.status == "triggered" else "legacy_open", {"holding_id": legacy.id}, clock=lambda: legacy.created_at or utc_now())
        db.flush()
        trigger_event = db.query(PositionEvent).filter(
            PositionEvent.position_id == position.id, PositionEvent.event_type.in_(("legacy_triggered", "legacy_closed")),
        ).order_by(PositionEvent.id.desc()).first()
        for alert in db.query(Alert).filter(Alert.holding_id == legacy.id).all():
            alert.position_id = position.id
            alert.trigger_event_id = trigger_event.id if trigger_event else None
            alert.disposition = alert.disposition or ("closed" if legacy.status == "closed" else "triggered")
        count += 1
    state.shadow_dirty, state.readiness_reason = False, None
    return {"projected": count}


def reconcile_shadow(db: Session) -> dict:
    """Compare non-sensitive accounting facts before allowing authority cutover."""
    legacy_rows = db.query(Holding).order_by(Holding.id).all()
    positions = db.query(Position).all()
    projected_by_identity: dict[tuple[str, str], list[Position]] = {}
    for position in positions:
        instrument = db.get(Instrument, position.instrument_id)
        if instrument is not None:
            projected_by_identity.setdefault((instrument.asset_type, instrument.code), []).append(position)
    mismatches: set[str] = set()
    if len(legacy_rows) != len(positions):
        mismatches.add("position_count")
    legacy_by_identity: dict[tuple[str, str], list[Holding]] = {}
    for row in legacy_rows:
        legacy_by_identity.setdefault((row.type, row.code), []).append(row)
    for identity, legacy_group in legacy_by_identity.items():
        position_group = projected_by_identity.get(identity, [])
        if not position_group:
            mismatches.add("instrument_identity")
            continue
        if len(legacy_group) != len(position_group):
            mismatches.add("position_count")
        expected_quantity = sum((Decimal(str(row.quantity)) for row in legacy_group if row.status != "closed"), Decimal("0"))
        actual_quantity = sum((Decimal(str(position.remaining_quantity)) for position in position_group if position.lifecycle_status == "open"), Decimal("0"))
        if actual_quantity != expected_quantity:
            mismatches.add("quantity")
        expected_states = sorted(row.status for row in legacy_group)
        actual_states = sorted(_legacy_status(position) for position in position_group)
        if actual_states != expected_states:
            mismatches.add("state")
        expected_stops = sorted(Decimal(str(row.stop_loss_price)) for row in legacy_group)
        actual_stops = []
        for position in position_group:
            rule = db.query(StopRule).filter(StopRule.position_id == position.id).order_by(StopRule.version.desc()).first()
            if rule is not None:
                actual_stops.append(Decimal(str(rule.stop_price)))
        if sorted(actual_stops) != expected_stops:
            mismatches.add("stop_rule")
        positions_by_rule = {Decimal(str(rule.stop_price)): position for position in position_group if (rule := db.query(StopRule).filter(StopRule.position_id == position.id).order_by(StopRule.version.desc()).first()) is not None}
        for row in legacy_group:
            position = positions_by_rule.get(Decimal(str(row.stop_loss_price)))
            if position is None:
                continue
            alerts = db.query(Alert).filter(Alert.holding_id == row.id).all()
            if any(alert.position_id != position.id for alert in alerts):
                mismatches.add("alerts")
    # Both views must account for the same currently open cost total. Closed legacy
    # records have no remaining balance and are intentionally excluded.
    legacy_cost = sum((Decimal(str(row.buy_price)) * Decimal(str(row.quantity)) for row in legacy_rows if row.status != "closed"), Decimal("0"))
    projected_cost = sum((Decimal(str(row.remaining_cost)) for row in positions if row.lifecycle_status == "open"), Decimal("0"))
    if legacy_cost != projected_cost:
        mismatches.add("dashboard_totals")
    matched = not mismatches
    state = authority(db)
    state.shadow_dirty, state.readiness_reason = (not matched), (None if matched else "shadow_reconciliation_mismatch")
    return {"matched": matched, "legacy_count": len(legacy_rows), "position_count": len(positions), "reason": state.readiness_reason, "mismatches": sorted(mismatches)}


def begin_shadow_read(db: Session) -> dict:
    state = authority(db)
    if state.stage != "legacy":
        raise ValueError("shadow_read_not_allowed")
    rebuild_shadow(db)
    reconciliation = reconcile_shadow(db)
    if not reconciliation["matched"]:
        raise ValueError("shadow_reconciliation_mismatch")
    state.stage = "shadow-read"
    return reconciliation


def project_after_legacy_commit(db: Session) -> None:
    """Project only after a successful legacy commit; failures never roll it back."""
    if authority(db).stage != "shadow-read":
        return
    try:
        rebuild_shadow(db)
        if not reconcile_shadow(db)["matched"]:
            raise ValueError("shadow_reconciliation_mismatch")
        db.commit()
    except Exception:
        db.rollback()
        mark_shadow_dirty(db)
        db.commit()


def cutover(db: Session) -> None:
    state = authority(db)
    if state.stage not in {"legacy", "shadow-read"} or state.shadow_dirty or not reconcile_shadow(db)["matched"]:
        raise ValueError("cutover_not_ready")
    state.stage, state.readiness_reason = "new-authoritative", None
