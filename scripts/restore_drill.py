from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from migrations import backup_database, restore_database  # noqa: E402


def main() -> int:
    temp_root = Path(os.environ.get("STOP_LOSS_TEMP_DIR", ROOT / ".tmp"))
    temp_root.mkdir(parents=True, exist_ok=True)
    work = temp_root / f"restore-drill-{uuid.uuid4().hex}"
    work.mkdir(parents=True)
    source = work / "source.db"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO schema_migrations VALUES (7)")
        conn.execute("CREATE TABLE evidence (value TEXT NOT NULL)")
        conn.execute("INSERT INTO evidence VALUES ('verified')")
    backup, manifest = backup_database(f"sqlite:///{source.as_posix()}", work / "backups")
    target = work / "target.db"
    restore_database(backup, manifest, target)
    assert not target.with_suffix(".restore.tmp").exists()
    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT value FROM evidence").fetchone()[0] == "verified"
    assert not target.with_suffix(".restore.tmp").exists()

    invalid = work / "backups" / "invalid.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["sha256"] = "0" * 64
    invalid.write_text(json.dumps(data), encoding="utf-8")
    try:
        restore_database(backup, invalid, target)
    except ValueError:
        pass
    else:
        raise AssertionError("损坏 manifest 未被拒绝")
    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT value FROM evidence").fetchone()[0] == "verified"
    print("备份恢复演练通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
