import pytest
from pathlib import Path
import json
from migrations import restore_database

from services.csv_portability import SCHEMA, preview_csv


def test_preview_is_zero_write_and_rejects_oversized_content():
    content=(",".join(SCHEMA)+"\n1,000001,=name,stock,10,10,fixed,9\n").encode()
    preview=preview_csv(content)
    assert preview["valid"] == 1 and preview["rows"][0]["data"]["name"] == "=name"
    with pytest.raises(ValueError, match="import_too_large"):
        preview_csv(b"x" * 8, max_bytes=1)

def test_restore_rejects_incompatible_manifest(tmp_path: Path):
    backup = tmp_path / "backup.db"; backup.write_bytes(b"not-a-database")
    manifest = tmp_path / "backup.json"; manifest.write_text(json.dumps({"sha256": "bad", "schema_version": 999}))
    with pytest.raises(ValueError): restore_database(backup, manifest, tmp_path / "target.db")
