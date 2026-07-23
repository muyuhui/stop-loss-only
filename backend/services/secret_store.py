from __future__ import annotations

"""Machine-local secret storage.  Secrets are never persisted in ``settings``."""
import base64
import os
from pathlib import Path

from config import config


def _path(name: str) -> Path:
    root = config.temp_dir / "secrets"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{name}.bin"


def set_secret(name: str, value: str) -> None:
    if os.name != "nt":
        raise ValueError("machine_secret_storage_unsupported")
    try:
        import win32crypt
    except ImportError as exc:
        raise ValueError("machine_secret_storage_unavailable") from exc
    protected = win32crypt.CryptProtectData(value.encode("utf-8"), None, None, None, None, 0)[1]
    _path(name).write_bytes(base64.b64encode(protected))


def get_secret(name: str) -> str | None:
    path = _path(name)
    if not path.exists(): return None
    try:
        import win32crypt
        return win32crypt.CryptUnprotectData(base64.b64decode(path.read_bytes()), None, None, None, 0)[1].decode("utf-8")
    except Exception:
        return None


def clear_secret(name: str) -> None:
    path = _path(name)
    if path.exists(): path.unlink()
