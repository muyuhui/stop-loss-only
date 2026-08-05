# 桌面通知：止损触发的本地送达通道

## Why

当前告警送达依赖前端浏览器标签页：浏览器关闭（例如工作演示场景）时，触发止损的告警只躺在 SQLite 里，用户事后才看见——这正是本工具存在的理由"触发时必须知道"的断点。用户工作环境要求通知**经得起被看到**：不能出现持仓名称/代码/价格。本 change 让后端在告警提交后直接发 Windows 本地通知，不依赖浏览器，并提供脱敏内容与演示暂停模式。

## What Changes

- 新增后端桌面通知服务（`services/desktop_notifier.py`）：告警提交后发送单条汇总 toast；通知器为可注入适配器（Windows `winotify` 实现 + fixture JSONL 实现，沿用 provider/fixture 模式），发送失败不影响监控事实（post-commit 隔离）。
- `monitoring.py` 在周期提交后调用通知器（同一钩子覆盖调度刷新与手动刷新两条触发路径），每次周期最多一条汇总通知。
- 新增三个持久化设置（`/api/settings`）：`desktop_notifications_enabled`（默认关，opt-in）、`desktop_notification_mode`（`full` / `redacted`，默认 `full`）、`desktop_notifications_paused`（演示模式，默认关）。
  - `full`：toast 含持仓名称/代码/价格。
  - `redacted`：toast 只含通用文案"有 N 笔触发待处理"，**不出现任何持仓信息**（名称、代码、价格、甚至"止损"字样），Windows 通知中心历史同样安全。
  - `paused`：完全静音，不发送任何 toast。
- 运行时能力 `desktop_notifications` 加入 `RuntimeCapabilities`（legacy/shadow-read 为 true），发送前检查，fail-before-side-effect。
- 前端设置页通知区新增三个控件（启用、内容模式、演示模式），通过 `PUT /api/settings` 持久化（不进 localStorage——通知由后端发送，模式必须后端知道）。
- 测试：后端通知器单测（模式矩阵、暂停、能力门、失败隔离）、监控集成测试（fixture 通知器断言 payload）、设置契约测试；E2E 用 fixture 通知器写 JSONL 文件断言脱敏/完整内容与暂停语义。
- 依赖：`winotify`（Windows 10+ 原生 toast，pip 精确 pin）。
- README 通知章节补充桌面通道说明。

## Capabilities

### New Capabilities

（无——不引入新运行面能力）

### Modified Capabilities

- `notification-delivery`: 新增桌面通知通道需求（汇总 toast、脱敏/完整模式、演示暂停、post-commit 失败隔离、能力门）
- `runtime-settings`: 新增三个持久化设置键的契约（默认值、校验、响应字段）

## Impact

- 后端: `backend/services/desktop_notifier.py`（新增）、`backend/services/monitoring.py`（收集告警 + 提交后分发）、`backend/routers/settings.py`（键集合 + BOOL_KEYS）、`backend/schemas.py`（`SettingsResponse`/`SettingsUpdate` 字段）、`backend/services/supported_runtime.py`（capability）、`backend/requirements.txt`（winotify pin）
- 前端: `frontend/src/views/Settings.vue`（通知区控件）
- 测试: `backend/tests/`（通知器/监控集成/设置契约）、`frontend/tests/`（mount）、`frontend/tests/e2e/`（fixture JSONL 断言）
- E2E 环境: `frontend/tests/e2e/global-setup.js`（fixture 通知路径 env）
- 文档: `README.md`
- 无数据库 schema 变更、无迁移、无新端点。
