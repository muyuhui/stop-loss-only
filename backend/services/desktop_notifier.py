from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from sqlalchemy.orm import Session

from config import config
from models import Alert, Setting
from services.shadow_projection import authority
from services.stop_loss import to_decimal
from services.supported_runtime import capability_available


logger = logging.getLogger(__name__)

try:
    from winotify import Notification
except ImportError:  # 非 Windows 或无 winotify 时降级为静默，绝不向调用方抛出
    Notification = None


DESKTOP_NOTIFICATION_KEYS = (
    "desktop_notifications_enabled",
    "desktop_notification_mode",
    "desktop_notifications_paused",
)

FULL_TITLE = "止损触发提醒"
REDACTED_TITLE = "提醒"


@dataclass(frozen=True)
class DesktopSummary:
    count: int
    items: tuple[dict, ...] = ()


class DesktopNotifier(Protocol):
    def send(self, summary: DesktopSummary, mode: str) -> None: ...


def _price(value) -> str:
    return f"{float(to_decimal(value)):.2f}"


def render_toast(summary: DesktopSummary, mode: str) -> tuple[str, str]:
    """按模式构造 toast 标题与正文；redacted 模式零持仓信息（含"止损"字样）。"""
    if mode == "redacted":
        return REDACTED_TITLE, f"有 {summary.count} 笔触发待处理"
    if summary.count == 1:
        item = summary.items[0]
        return FULL_TITLE, (
            f"{item['name']}（{item['code']}）现价 {_price(item['current_price'])} / 止损 {_price(item['trigger_price'])}"
        )
    shown = "、".join(f"{item['name']}（{item['code']}）" for item in summary.items[:3])
    return FULL_TITLE, f"{shown} 等 {summary.count} 笔触发止损"


class WinToastNotifier:
    """Windows 10+ 原生 toast；winotify 缺失时静默降级（仅 debug 日志）。"""

    def send(self, summary: DesktopSummary, mode: str) -> None:
        if Notification is None:
            logger.debug("desktop_notify_unavailable", extra={"reason": "winotify_missing"})
            return
        title, body = render_toast(summary, mode)
        toast = Notification(app_id="止损不止盈", title=title, msg=body, duration="short")
        toast.show()


class FixtureNotifier:
    """离线测试实现：把渲染后的 toast（与用户所见一致）以 JSONL 追加写入配置路径。"""

    def send(self, summary: DesktopSummary, mode: str) -> None:
        if not config.desktop_notify_path:
            logger.debug("desktop_notify_fixture_no_path")
            return
        path = Path(config.desktop_notify_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        title, body = render_toast(summary, mode)
        record = {
            "mode": mode,
            "title": title,
            "body": body,
            "count": summary.count,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def resolve_notifier() -> DesktopNotifier:
    if config.desktop_notify_fixture_enabled:
        return FixtureNotifier()
    return WinToastNotifier()


def desktop_notify_triggered(db: Session, alerts: list[Alert]) -> None:
    """告警提交后调用：未启用/演示暂停/能力不可用/无告警时不做任何事；异常不外溢。

    直接读取 Setting 行（不 import router），发送失败只记日志，绝不影响监控事实。
    """
    if not alerts:
        return
    if not capability_available(authority(db).stage, "desktop_notifications"):
        return
    rows = {
        row.key: row.value
        for row in db.query(Setting).filter(Setting.key.in_(DESKTOP_NOTIFICATION_KEYS)).all()
    }
    if rows.get("desktop_notifications_enabled") != "True":
        return
    if rows.get("desktop_notifications_paused") == "True":
        return
    mode = rows.get("desktop_notification_mode", "full")
    if mode not in ("full", "redacted"):
        mode = "full"
    summary = DesktopSummary(
        count=len(alerts),
        items=tuple({
            "name": alert.holding_name,
            "code": alert.holding_code,
            "current_price": float(to_decimal(alert.current_price)),
            "trigger_price": float(to_decimal(alert.trigger_price)),
        } for alert in alerts),
    )
    try:
        resolve_notifier().send(summary, mode)
    except Exception:
        logger.warning("desktop_notify_failed", exc_info=True)
