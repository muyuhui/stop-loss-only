from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from database import Base
import models  # noqa: F401 - 注册 ORM metadata


LATEST_SCHEMA_VERSION = 7


def sqlite_path(database_url: str) -> Path:
    parsed = urlparse(database_url)
    return Path(parsed.path.lstrip("/")) if parsed.netloc else Path(database_url.removeprefix("sqlite:///"))


def backup_database(database_url: str, target_dir: Path) -> tuple[Path, Path]:
    source = sqlite_path(database_url).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = target_dir / f"stop_loss-{stamp}.db"
    if source.exists():
        with sqlite3.connect(source) as src, sqlite3.connect(backup) as dst:
            src.backup(dst)
    else:
        sqlite3.connect(backup).close()
    digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    manifest = backup.with_suffix(".json")
    with sqlite3.connect(backup) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    manifest.write_text(json.dumps({"sha256": digest, "schema_version": current_version_file(backup), "created_at": datetime.now().isoformat(), "integrity_check": integrity, "wal_present": source.with_name(source.name + "-wal").exists()}, ensure_ascii=False, indent=2), encoding="utf-8")
    return backup, manifest


def current_version_file(path: Path) -> int:
    if not path.exists():
        return 0
    with sqlite3.connect(path) as conn:
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'").fetchone()
        if not exists:
            return 0
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return int(row[0] or 0)


def current_version(engine) -> int:
    if "schema_migrations" not in inspect(engine).get_table_names():
        return 0
    with engine.connect() as conn:
        return int(conn.execute(text("SELECT COALESCE(MAX(version), 0) FROM schema_migrations")).scalar_one())


def upgrade(engine, database_url: str, backup_dir: Path | None = None) -> None:
    tables = set(inspect(engine).get_table_names())
    version_before = current_version(engine)
    if tables and "schema_migrations" not in tables and backup_dir is not None:
        backup_database(database_url, backup_dir)
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    holding_columns = {c["name"] for c in inspector.get_columns("holdings")} if "holdings" in inspector.get_table_names() else set()
    alert_columns = {c["name"] for c in inspector.get_columns("alerts")} if "alerts" in inspector.get_table_names() else set()
    holding_additions = {
        "quote_source": "VARCHAR(50)", "quoted_at": "DATETIME", "fetched_at": "DATETIME",
        "quote_state": "VARCHAR(20) NOT NULL DEFAULT 'unpriced'", "fresh_until": "DATETIME",
        "is_actionable": "BOOLEAN NOT NULL DEFAULT 0", "quote_error_code": "VARCHAR(50)",
        "last_cycle_id": "VARCHAR(32)", "version": "INTEGER NOT NULL DEFAULT 1",
        "trigger_sequence": "INTEGER NOT NULL DEFAULT 0",
    }
    alert_additions = {
        "holding_name": "VARCHAR(100) NOT NULL DEFAULT ''", "holding_code": "VARCHAR(20) NOT NULL DEFAULT ''",
        "lifecycle_key": "VARCHAR(64)", "quote_source": "VARCHAR(50)", "quoted_at": "DATETIME",
        "idempotency_key": "VARCHAR(64)", "cycle_id": "VARCHAR(32)",
        "position_id": "INTEGER", "trigger_event_id": "INTEGER", "disposition": "VARCHAR(20)",
    }
    with engine.begin() as conn:
        for name, ddl in holding_additions.items():
            if name not in holding_columns:
                conn.execute(text(f"ALTER TABLE holdings ADD COLUMN {name} {ddl}"))
        for name, ddl in alert_additions.items():
            if name not in alert_columns:
                conn.execute(text(f"ALTER TABLE alerts ADD COLUMN {name} {ddl}"))
        if "holdings" in tables:
            conn.execute(text("UPDATE holdings SET status='closed' WHERE status='stopped_out'"))
            conn.execute(text("UPDATE holdings SET quote_state=CASE WHEN quote_source IS NULL THEN 'unpriced' ELSE 'stale' END, is_actionable=0 WHERE quote_state IS NULL OR quote_state='unpriced'"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_holdings_quote_state ON holdings(quote_state)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_holdings_last_cycle_id ON holdings(last_cycle_id)"))
        if "alerts" in tables:
            conn.execute(text("UPDATE alerts SET holding_name=COALESCE((SELECT name FROM holdings WHERE holdings.id=alerts.holding_id), holding_name, ''), holding_code=COALESCE((SELECT code FROM holdings WHERE holdings.id=alerts.holding_id), holding_code, ''), lifecycle_key=COALESCE(lifecycle_key, 'legacy-' || id)"))
            conn.execute(text("UPDATE alerts SET idempotency_key=COALESCE(idempotency_key, lifecycle_key)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_alert_holding_lifecycle_idx ON alerts(holding_id, lifecycle_key)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_alert_idempotency_key ON alerts(idempotency_key)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_alerts_cycle_id ON alerts(cycle_id)"))
        # v7 creates delivery/import/retention tables through metadata above.  The
        # explicit indexes make upgrades from all earlier schemas deterministic.
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_delivery_attempt_due ON delivery_attempts(status, next_attempt_at)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_delivery_attempt_idempotency ON delivery_attempts(idempotency_key)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL)"))
        for version in range(1, LATEST_SCHEMA_VERSION + 1):
            conn.execute(text("INSERT OR IGNORE INTO schema_migrations(version) VALUES (:version)"), {"version": version})
        conn.execute(text("INSERT OR IGNORE INTO migration_authority(id, stage, shadow_dirty) VALUES (1, 'legacy', 0)"))
    # Establish the initial read-only shadow from the legacy authority.  A failed
    # projection never changes holdings; it merely requires a later idempotent
    # `shadow-rebuild` before any authority transition.
    if version_before < LATEST_SCHEMA_VERSION and "holdings" in tables:
        from services.shadow_projection import mark_shadow_dirty, rebuild_shadow, reconcile_shadow
        db = Session(bind=engine)
        try:
            rebuild_shadow(db)
            if not reconcile_shadow(db)["matched"]:
                raise ValueError("shadow_reconciliation_mismatch")
            db.commit()
        except Exception:
            db.rollback()
            mark_shadow_dirty(db, "initial_shadow_projection_failed")
            db.commit()
            raise
        finally:
            db.close()


def downgrade(engine) -> None:
    if current_version(engine) != LATEST_SCHEMA_VERSION:
        raise ValueError("数据库不在可降级的最新版本")
    with engine.begin() as conn:
        # v4 only adds backward-compatible columns, indexes, and diagnostics tables.
        # Keep them in place so rollback is non-destructive; older code ignores them.
        conn.execute(text("DELETE FROM schema_migrations WHERE version=:version"), {"version": LATEST_SCHEMA_VERSION})


def restore_database(backup: Path, manifest: Path, target: Path) -> None:
    if backup.resolve().parent != manifest.resolve().parent:
        raise ValueError("backup_manifest_path_mismatch")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if hashlib.sha256(backup.read_bytes()).hexdigest() != data["sha256"]:
        raise ValueError("备份校验和不匹配")
    if int(data.get("schema_version", 0)) > LATEST_SCHEMA_VERSION: raise ValueError("backup_schema_unsupported")
    with sqlite3.connect(backup) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("备份完整性校验失败")
    recovery = target.with_suffix(".recovery.db")
    if target.exists(): shutil.copy2(target, recovery)
    temporary = target.with_suffix(".restore.tmp")
    try:
        shutil.copy2(backup, temporary)
        with sqlite3.connect(temporary) as conn:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok": raise ValueError("restore_readiness_failed")
        shutil.copy2(temporary, target)
    except Exception:
        if recovery.exists(): shutil.copy2(recovery, target)
        raise
