# Design — 桌面通知：止损触发的本地送达通道

## Context

- 送达现状：`App.vue` 轮询 + 浏览器通知，全部依赖前端标签页存活；浏览器关闭即断送。
- 后端钩子已存在：`services/monitoring.py` 在 `db.commit(); project_after_legacy_commit(db)` 之后有一处显式注释"delivery work is optional and may fail independently without rolling back facts"——`enqueue_committed_alerts` 的先例，桌面通知复用同一钩子位置。该函数同时被调度器与手动刷新调用，单点覆盖两条路径。
- 告警在监控循环内创建（带 `cycle_id`），可收集后传递，无需重查。
- 设置机制：`Setting` 键值表（`key`/`value` 字符串），`routers/settings.py` 用 `DEFAULTS`/`INTEGER_KEYS`/`DECIMAL_KEYS`/`PERSISTED_SETTING_KEYS` 管理；`SettingsUpdate` 以 `model_dump(exclude_none=True)` 合并；无 BOOL 键先例（需要新增 `BOOL_KEYS`）。
- 能力门先例：`RuntimeCapabilities.browser_notifications` 在 legacy/shadow-read 为 true，`supported_runtime.py` 统一声明。
- fixture 适配器先例：`FixtureQuoteProvider`/`FixtureDeepSeekProvider`——E2E/smoke 通过 env 切换确定性实现。
- 用户约束：通知可能出现在领导面前的屏幕上，`redacted` 模式必须连"止损"字样都不出现；Windows 通知中心历史同样只含已发送内容。
- winotify 1.1.0（pip 最新版，Windows 10+ toast；非 Windows 导入失败需守卫）。

## Goals / Non-Goals

**Goals:**
- 浏览器关闭时，触发止损仍通过 Windows 本地通知送达。
- 三种语义：完整（full）/ 脱敏（redacted）/ 演示暂停（paused），全部后端持久化。
- 通知失败绝不影响监控事实（post-commit、try/except、只记日志）。
- 可离线测试：fixture 通知器写 JSONL，E2E 断言内容。

**Non-Goals:**
- 不做浏览器通知的替代（两条通道并存，`notify-on-trigger` 逻辑不动）。
- 不做定时免打扰（交易时段≈工作时间，定时静音是陷阱）；只做手动暂停。
- 不做通知历史清理、不做多通知合并策略之外的分组（每次周期最多一条）。
- 不新增 API 端点；不新增 DB 迁移。

## Decisions

### D1: 通知器抽象 — 可注入适配器（沿用 provider 模式）
- `services/desktop_notifier.py` 定义 `DesktopNotifier(Protocol)`：`send(summary: DesktopSummary) -> None`。
- `WinToastNotifier`：winotify 实现（`try: from winotify import Notification except ImportError: Notification = None`，非 Windows 或无 winotify 时降级为 no-op + debug 日志，绝不抛错）。
- `FixtureNotifier`：`STOP_LOSS_DESKTOP_NOTIFY_FIXTURE=1` 时启用，把 summary 按 JSONL 追加写入 `STOP_LOSS_DESKTOP_NOTIFY_PATH`（E2E global-setup 提供），供测试断言。
- 选择逻辑与 provider 一致：从 env/config 决定，测试注入 override。
- 备选：直接调 winotify——被拒：不可离线测试、非 Windows 直接崩。

### D2: 设置键 — 三个持久化键 + BOOL_KEYS
- `desktop_notifications_enabled: bool`（默认 `False`，opt-in，与浏览器通知先例一致）
- `desktop_notification_mode: Literal["full", "redacted"]`（默认 `"full"`）
- `desktop_notifications_paused: bool`（默认 `False`）
- `routers/settings.py`：新增 `BOOL_KEYS = {"desktop_notifications_enabled", "desktop_notifications_paused"}`（读取时 `value == "True"`）；键加入 `DEFAULTS`（False/False、"full"）与 `PERSISTED_SETTING_KEYS`；`SettingsUpdate` 字段 `bool | None` 与 `Literal | None`（非法 mode → 422，Pydantic 自动）。
- 注意：`get_effective_settings` 的 `for` 循环目前只处理 INTEGER/DECIMAL/时间戳——新增 BOOL 分支。

### D3: 分发点 — monitoring.py 提交后钩子，每次周期最多一条汇总
- 监控循环内收集本周期创建的告警（循环中已有 alert 构造点；收集列表，`cycle_id` 防串扰）。
- `db.commit(); project_after_legacy_commit(db)` 之后调用 `desktop_notify_triggered(db, created_alerts)`：
  - 读设置（三键）+ 能力检查（`desktop_notifications`）→ 未启用/暂停/能力不可用 → 直接返回。
  - 无告警 → 返回。
  - 构造 `DesktopSummary`：`count`、`items`（每笔 name/code/price，仅 full 用）。
  - 按 mode 生成 payload → 调 notifier。
  - 整个调用包 try/except，异常只 `logger.warning("desktop_notify_failed", ...)`，绝不回滚、不影响周期结果。
- 覆盖：调度刷新与手动刷新共用 `run_monitoring_cycle`，单钩子双覆盖。

### D4: 内容模式 — redacted 零持仓信息
- `full`：标题 `止损触发提醒`，正文 `平安银行（000001）现价 ¥8.80 / 止损 ¥9.00`，多笔时 `平安银行（000001）等 N 笔触发止损`（最多列出前 3 笔名称+代码，其余计数）。
- `redacted`：标题 `提醒`，正文 `有 N 笔触发待处理`。**无名称、代码、价格、无"止损"字样**；Windows 通知中心历史因此安全。
- 金额格式化复用后端 `decimal_string` 风格（str，不引前端）。

### D5: 能力门 — `desktop_notifications` capability
- `RuntimeCapabilities` 增加 `desktop_notifications: bool = False`；`supported_runtime.py` 在 legacy/shadow-read 置 `True`（与 `browser_notifications` 一致），new-authoritative 为 False。
- 分发前检查（fail-before-side-effect）；设置键本身不 gate（惰性键，无副作用）。

### D6: 前端设置 UI
- `Settings.vue` 通知区（浏览器通知区旁）新增"桌面通知"子区：启用开关、内容模式单选（完整/脱敏）、演示模式开关（启用时显示"暂停全部桌面通知"状态）。
- 走现有 `saveSettings`（`PUT /api/settings`）；设置 store 的 `apply()` 增加三键映射；`fetchSettings` 返回后回填。
- 演示模式开关语义：打开 = `desktop_notifications_paused: true`；关闭恢复。文案明确"演示或共享屏幕时打开"。

### D7: 测试策略
- 后端单测（`test_desktop_notifier.py`，mock notifier 与 Setting 行）：
  - 未启用 / paused / 能力 False / 无告警 → 不发送
  - full：payload 含名称/代码/价格；redacted：payload 不含名称/代码/价格且标题为"提醒"
  - 多笔：正文含"N 笔"且最多列 3 笔
  - notifier 抛异常 → 不冒泡（周期结果不受影响）
- 监控集成：fixture 通知器注入，跑周期断言收到 summary 且 JSONL 内容正确；手动刷新路径同一断言。
- 设置契约：三键默认值、PUT 持久化与回读、非法 mode → 422、BOOL 读写。
- E2E：global-setup 设 `STOP_LOSS_DESKTOP_NOTIFY_FIXTURE=1` + `STOP_LOSS_DESKTOP_NOTIFY_PATH=<runRoot>/desktop-notify.jsonl`；场景：设置页开启桌面通知 + redacted → 触发一笔止损 → 读 JSONL 断言无名称/代码/价格；切 full → 断言含名称；paused → 不再追加。
- 既有浏览器通知 E2E 全部保持通过（双通道并存）。

## Risks / Trade-offs

- [winotify 在非 Windows 导入失败] → import 守卫 + no-op 降级；fixture 通知器与平台无关，测试不依赖 Windows。
- [toast 弹出时机与内容被旁人看到] → redacted 默认文案零敏感；paused 完全静音；full 是用户显式选择。
- [批量触发多条告警刷屏] → 每次周期最多一条汇总 toast（full 列前 3 笔 + 计数）。
- [通知失败拖垮周期] → post-commit + try/except + 只记日志（沿用 delivery.py 注释确立的隔离原则）。
- [设置读取与路由层耦合] → 通知器直接查 `Setting` 行，不 import router（保持 service 层方向）。

## Migration Plan

- 无数据库迁移（Setting 表即插即用）。`winotify` 由 `setup.ps1` 的 pip 流程安装。
- 回滚：还原代码即可；设置键为纯增量，旧前端忽略。

## Open Questions

- 无阻塞性问题。winotify pin 版本 1.1.0（安装时以 pip 解析结果为准，精确 `==` pin）。
