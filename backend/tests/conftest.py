from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from network_guard import install_network_sentinel, uninstall_network_sentinel  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def hermetic_network_and_tempdir():
    temp_dir = ROOT / ".tmp" / "pytest"
    temp_dir.mkdir(parents=True, exist_ok=True)
    previous = {name: os.environ.get(name) for name in ("TMP", "TEMP", "STOP_LOSS_TEMP_DIR")}
    os.environ.update({"TMP": str(temp_dir), "TEMP": str(temp_dir), "STOP_LOSS_TEMP_DIR": str(temp_dir)})
    # Starlette's Windows test event loop uses a loopback socketpair internally.
    # Preserve local IPC while rejecting every external DNS lookup and connection.
    install_network_sentinel(allow_loopback=True)
    try:
        yield
    finally:
        uninstall_network_sentinel()
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
