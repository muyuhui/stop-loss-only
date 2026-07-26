from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from migrations import LATEST_SCHEMA_VERSION, backup_database, restore_database
from services.supported_runtime import authority_readiness


def _database(path: Path, *, authority: str = "legacy") -> str:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO schema_migrations VALUES (?)", (LATEST_SCHEMA_VERSION,))
        conn.execute("CREATE TABLE migration_authority (id INTEGER PRIMARY KEY, stage TEXT NOT NULL)")
        conn.execute("INSERT INTO migration_authority VALUES (1, ?)", (authority,))
        conn.execute("CREATE TABLE evidence (value TEXT NOT NULL)")
        conn.execute("INSERT INTO evidence VALUES ('original')")
    return f"sqlite:///{path.as_posix()}"


def test_same_second_backups_are_unique_and_record_wal_state(tmp_path: Path):
    source = tmp_path / "source.db"
    url = _database(source)
    with sqlite3.connect(source) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("INSERT INTO evidence VALUES ('wal')")
        first = backup_database(url, tmp_path / "backups")
        second = backup_database(url, tmp_path / "backups")
    assert first[0] != second[0]
    assert first[0].exists() and second[0].exists()
    assert json.loads(first[1].read_text(encoding="utf-8"))["wal_present"] is True


@pytest.mark.parametrize("failure", ["checksum", "schema", "integrity"])
def test_invalid_backup_never_replaces_active_database(tmp_path: Path, failure: str):
    source = tmp_path / "source.db"
    target = tmp_path / "target.db"
    url = _database(source)
    _database(target)
    backup, manifest = backup_database(url, tmp_path / "backups")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if failure == "checksum":
        data["sha256"] = "0" * 64
    elif failure == "schema":
        data["schema_version"] = LATEST_SCHEMA_VERSION + 1
    else:
        backup.write_bytes(b"not sqlite")
        data["sha256"] = hashlib.sha256(backup.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises((ValueError, sqlite3.DatabaseError)):
        restore_database(backup, manifest, target)

    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT value FROM evidence").fetchone()[0] == "original"


def test_restore_preserves_recovery_point_and_new_authority_stays_not_ready(tmp_path: Path):
    source = tmp_path / "source.db"
    target = tmp_path / "target.db"
    url = _database(source, authority="new-authoritative")
    _database(target)
    backup, manifest = backup_database(url, tmp_path / "backups")
    restore_database(backup, manifest, target)
    recovery = target.with_suffix(".recovery.db")
    assert recovery.exists()
    with sqlite3.connect(recovery) as conn:
        assert conn.execute("SELECT value FROM evidence").fetchone()[0] == "original"
    with sqlite3.connect(target) as conn:
        stage = conn.execute("SELECT stage FROM migration_authority WHERE id=1").fetchone()[0]
    supported, detail = authority_readiness(stage)
    assert supported is False and detail["error_code"] == "new_authority_not_supported"
