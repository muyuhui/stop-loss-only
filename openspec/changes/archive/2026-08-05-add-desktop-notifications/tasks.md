# Tasks — 桌面通知：止损触发的本地送达通道

## 1. 通知器服务

- [x] 1.1 `backend/requirements.txt` 增加 `winotify==1.1.0`（安装时以 pip 解析为准的精确 pin）
  **验收**：`setup.ps1` 可安装；非 Windows 环境导入失败不影响测试（import 守卫）
- [x] 1.2 新增 `backend/services/desktop_notifier.py`：`DesktopSummary` dataclass（count + items）、`DesktopNotifier` Protocol、`WinToastNotifier`（winotify，import 守卫 + no-op 降级）、`FixtureNotifier`（`STOP_LOSS_DESKTOP_NOTIFY_FIXTURE=1` 时把 summary JSONL 追加写入 `STOP_LOSS_DESKTOP_NOTIFY_PATH`）、`resolve_notifier()` 选择逻辑
  **验收**：fixture 模式不触碰 winotify；写入 JSONL 含 count 与 items
- [x] 1.3 内容构造：`build_desktop_summary(alerts)` 与 `render_toast(summary, mode)`——`full` 标题"止损触发提醒"、正文列出前 3 笔名称+代码+价格（多笔附"等 N 笔"）；`redacted` 标题"提醒"、正文"有 N 笔触发待处理"（零持仓信息、无"止损"字样）
  **验收**：redacted payload 不含任何 name/code/price 字段值与"止损"字符串
- [x] 1.4 设置与能力读取：`desktop_notify_triggered(db, alerts)`——直接查 `Setting` 三键（不 import router）+ `capability_available(stage, "desktop_notifications")`；未启用/paused/能力不可用/无告警 → 不发送；发送全程 try/except，异常仅 `logger.warning`，不冒泡
  **验收**：任何异常路径都不影响调用方

## 2. 监控接入

- [x] 2.1 `backend/services/monitoring.py`：监控循环内收集本周期创建的告警列表；`db.commit(); project_after_legacy_commit(db)` 之后调用 `desktop_notify_triggered(db, created_alerts)`（与 delivery 注释同一钩子位置）
  **验收**：调度刷新与手动刷新两条路径都触发通知；通知失败时周期结果不变
- [x] 2.2 `backend/services/supported_runtime.py`：`RuntimeCapabilities` 增加 `desktop_notifications: bool = False`，legacy/shadow-read 置 `True`（与 `browser_notifications` 并列）；`backend/tests/test_supported_runtime.py` 相应断言更新
  **验收**：能力矩阵测试通过，`feature_not_supported` 语义不变

## 3. 设置契约

- [x] 3.1 `backend/routers/settings.py`：新增 `BOOL_KEYS`（`desktop_notifications_enabled`、`desktop_notifications_paused`）；三键加入 `DEFAULTS`（`False`/`"full"`/`False`）与 `PERSISTED_SETTING_KEYS`；`get_effective_settings` 增加 BOOL 分支（`value == "True"`）
  **验收**：默认值正确；PUT 后重启语义（回读）一致
- [x] 3.2 `backend/schemas.py`：`SettingsResponse` 增加 `desktop_notifications_enabled: bool`、`desktop_notification_mode: Literal["full", "redacted"]`、`desktop_notifications_paused: bool`；`SettingsUpdate` 对应可选字段
  **验收**：非法 mode → 422；`/api/settings` 序列化含三键
- [x] 3.3 设置契约测试：默认值、PUT 持久化与回读、非法 mode 422、BOOL 读写（并入 `test_api.py` 设置测试或新增用例）
  **验收**：`python -m pytest -p no:cacheprovider -q` 全绿

## 4. 后端通知测试

- [x] 4.1 新增 `backend/tests/test_desktop_notifier.py`（沿用内存库 bootstrap + fixture 通知器/mock）：
  **验收**：覆盖——未启用/暂停/能力 False/无告警不发送；full 含名称/代码/价格；redacted 零持仓信息且标题"提醒"；多笔最多列 3 笔 + 计数；notifier 抛异常不冒泡
- [x] 4.2 监控集成测试：跑周期（fixture 行情）断言通知器收到 summary、JSONL 内容与模式一致；手动刷新路径同一断言
  **验收**：与 `test_monitoring.py` 既有场景不冲突，全部通过

## 5. 前端设置 UI

- [x] 5.1 `frontend/src/views/Settings.vue` 通知区新增"桌面通知"子区：启用开关、内容模式单选（完整/脱敏）、演示模式开关（开启时提示"演示或共享屏幕时打开"）；提交走既有 `saveSettings`（`PUT /api/settings`）
  **验收**：三控件与后端设置双向同步（加载回填、保存成功回读）
- [x] 5.2 `frontend/src/stores/settings.js`：`apply()` 增加三键映射；`saveSettings` payload 包含三键
  **验收**：既有设置保存测试不回归
- [x] 5.3 mount 测试：渲染三控件、切换触发带三键的 PUT、加载时回填（扩展既有 settings mount spec 或新增）
  **验收**：`npm test` 通过

## 6. E2E

- [x] 6.1 `frontend/tests/e2e/global-setup.js`：后端 env 增加 `STOP_LOSS_DESKTOP_NOTIFY_FIXTURE=1` 与 `STOP_LOSS_DESKTOP_NOTIFY_PATH=<runRoot>/desktop-notify.jsonl`
  **验收**：E2E 后端启动使用 fixture 通知器
- [x] 6.2 `supported-runtime.spec.js` 新增场景：设置页开启桌面通知并选脱敏 → 触发一笔止损（`page.request.post('/api/prices/refresh')`）→ 读取 JSONL 断言无名称/代码/价格且含"待处理"；切换 full 再触发 → 断言含名称与代码；开启演示暂停再触发 → JSONL 不再追加；`assertPageIntegrity` 通过
  **验收**：三项目（mobile/tablet/desktop）全部通过，既有浏览器通知场景不回归

## 7. 文档与门禁

- [x] 7.1 README 通知章节补充桌面通知：启用方式、内容模式、演示暂停、脱敏保证（redacted 不含任何持仓信息）、与浏览器通知双通道并存
  **验收**：README 与实际行为一致
- [x] 7.2 运行 `.\verify.ps1` 全量门禁并修复所有回归
  **验收**：门禁全部通过
- [x] 7.3 `/opsx:sync` 同步 delta specs 进主 specs 后 `/opsx:archive`
  **验收**：主 spec `notification-delivery` 与 `runtime-settings` 含新需求；change 归档
