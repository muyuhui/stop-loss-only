from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import inspect, text

from database import Base
import models  # noqa: F401 - 注册 ORM metadata


LATEST_SCHEMA_VERSION = 2


def sqlite_path(database_url: str) -> Path:
    parsed = urlparse(database_url)
    return Path(parsed.path.lstrip("/")) if parsed.netloc else Path(database_url.removeprefix("sqlite:///"))


def backup_database(database_url: str, target_dir: Path) -> tuple[Path, Path]:
    source = sqlite_path(database_url).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = target_dir / f"stop_loss-{stamp}.db"
    if source.exists():
        with sqlite3.connect(source) as src, sqlite3.connect(backup) as dst:
            src.backup(dst)
    else:
        sqlite3.connect(backup).close()
    digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    manifest = backup.with_suffix(".json")
    manifest.write_text(json.dumps({"sha256": digest, "schema_version": current_version_file(backup), "created_at": datetime.now().isoformat()}, ensure_ascii=False, indent=2), encoding="utf-8")
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
    if tables and "schema_migrations" not in tables and backup_dir is not None:
        backup_database(database_url, backup_dir)
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    holding_columns = {c["name"] for c in inspector.get_columns("holdings")} if "holdings" in inspector.get_table_names() else set()
    alert_columns = {c["name"] for c in inspector.get_columns("alerts")} if "alerts" in inspector.get_table_names() else set()
    holding_additions = {
        "quote_source": "VARCHAR(50)", "quoted_at": "DATETIME", "fetched_at": "DATETIME",
    }
    alert_additions = {
        "holding_name": "VARCHAR(100) NOT NULL DEFAULT ''", "holding_code": "VARCHAR(20) NOT NULL DEFAULT ''",
        "lifecycle_key": "VARCHAR(64)", "quote_source": "VARCHAR(50)", "quoted_at": "DATETIME",
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
        if "alerts" in tables:
            conn.execute(text("UPDATE alerts SET holding_name=COALESCE((SELECT name FROM holdings WHERE holdings.id=alerts.holding_id), holding_name, ''), holding_code=COALESCE((SELECT code FROM holdings WHERE holdings.id=alerts.holding_id), holding_code, ''), lifecycle_key=COALESCE(lifecycle_key, 'legacy-' || id)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_alert_holding_lifecycle_idx ON alerts(holding_id, lifecycle_key)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL)"))
        conn.execute(text("INSERT OR IGNORE INTO schema_migrations(version) VALUES (:version)"), {"version": LATEST_SCHEMA_VERSION})


def downgrade(engine) -> None:
    if current_version(engine) != LATEST_SCHEMA_VERSION:
        raise ValueError("数据库不在可降级的最新版本")
    with engine.begin() as conn:
        conn.execute(text("UPDATE holdings SET status='stopped_out' WHERE status='closed'"))
        conn.execute(text("DELETE FROM schema_migrations WHERE version=:version"), {"version": LATEST_SCHEMA_VERSION})


def restore_database(backup: Path, manifest: Path, target: Path) -> None:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if hashlib.sha256(backup.read_bytes()).hexdigest() != data["sha256"]:
        raise ValueError("备份校验和不匹配")
    with sqlite3.connect(backup) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("备份完整性校验失败")
    temporary = target.with_suffix(".restore.tmp")
    shutil.copy2(backup, temporary)
    temporary.replace(target)
