from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

import uvicorn  # noqa: E402
from config import config  # noqa: E402
from database import engine  # noqa: E402
from migrations import upgrade  # noqa: E402


def main() -> None:
    upgrade(engine, config.database_url, config.temp_dir / "migration-backups")
    uvicorn.run("main:app", app_dir=str(BACKEND), host="127.0.0.1", port=config.backend_port, workers=1)


if __name__ == "__main__":
    main()
