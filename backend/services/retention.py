from __future__ import annotations
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from models import PositionQuote, RetentionState

def cleanup_quotes(db: Session, days: int, batch_size: int = 200) -> int:
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    rows = db.query(PositionQuote).filter(PositionQuote.recorded_at < cutoff).order_by(PositionQuote.id).limit(batch_size).all()
    for row in rows: db.delete(row)
    state = db.get(RetentionState, "position_quotes") or RetentionState(key="position_quotes")
    state.last_deleted, state.last_run_at = len(rows), datetime.now(timezone.utc)
    if state not in db: db.add(state)
    db.commit(); return len(rows)
