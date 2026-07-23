from __future__ import annotations

import argparse
from pathlib import Path

from config import config
from database import engine
from migrations import backup_database, current_version, downgrade, restore_database, sqlite_path, upgrade
from database import SessionLocal
from services.shadow_projection import begin_shadow_read, cutover, rebuild_shadow, reconcile_shadow


def main():
    parser = argparse.ArgumentParser(description="止损不止盈数据库管理")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("upgrade")
    sub.add_parser("downgrade")
    sub.add_parser("shadow-rebuild")
    sub.add_parser("shadow-enable")
    sub.add_parser("shadow-status")
    sub.add_parser("cutover")
    backup = sub.add_parser("backup")
    backup.add_argument("--output", default=str(Path(__file__).resolve().parent / "backups"))
    restore = sub.add_parser("restore")
    restore.add_argument("backup")
    restore.add_argument("manifest")
    args = parser.parse_args()
    if args.command == "status":
        print(current_version(engine))
    elif args.command == "upgrade":
        upgrade(engine, config.database_url, Path(__file__).resolve().parent / "backups")
        print(f"数据库已升级到版本 {current_version(engine)}")
    elif args.command == "downgrade":
        downgrade(engine)
        print(f"数据库已降级到版本 {current_version(engine)}")
    elif args.command in {"shadow-rebuild", "shadow-enable", "shadow-status", "cutover"}:
        db = SessionLocal()
        try:
            if args.command == "shadow-rebuild": print(rebuild_shadow(db)); print(reconcile_shadow(db)); db.commit()
            elif args.command == "shadow-enable": print(begin_shadow_read(db)); db.commit(); print("authority=shadow-read")
            elif args.command == "shadow-status": print(reconcile_shadow(db)); db.rollback()
            else:
                # This command is run with the application stopped, so no scheduler
                # or API writer can race the final rebuild/reconciliation.
                backup_database(config.database_url, Path(__file__).resolve().parent / "backups")
                rebuild_shadow(db)
                cutover(db)
                db.commit(); print("authority=new-authoritative")
        finally: db.close()
    elif args.command == "backup":
        paths = backup_database(config.database_url, Path(args.output))
        print(paths[0])
        print(paths[1])
    elif args.command == "restore":
        restore_database(Path(args.backup), Path(args.manifest), sqlite_path(config.database_url))
        print("数据库恢复完成")


if __name__ == "__main__":
    main()
