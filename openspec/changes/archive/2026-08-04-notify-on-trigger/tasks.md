## 1. 后端能力契约

- [x] 1.1 在 `backend/services/supported_runtime.py` 的 `RuntimeCapabilities` 新增 `browser_notifications: bool = False` 字段,并在 legacy 与 shadow-read 策略中声明为 True
- [x] 1.2 在 `backend/tests/test_supported_runtime.py` 补充断言:legacy/shadow-read 声明 `browser_notifications=True`,new-authoritative 与缺省为 False,Webhook 字段保持 False
- [x] 1.3 运行后端测试确认契约变更通过(`python -m pytest -p no:cacheprovider -q`)

## 2. 通知工具模块

- [x] 2.1 新建 `frontend/src/utils/notifications.js`:封装权限状态机(`granted`/`denied`/`unsupported`)、`ensurePermission()`(仅显式调用时请求)、`sendTriggerNotification(alert)`(构造标题/正文/点击跳转 `/holdings/:id`)、Web Audio 提示音(默认关闭)、每次发送前校验 `Notification.permission`
- [x] 2.2 编写 `frontend/tests/notifications.test.js`(node:test,mock 全局 Notification):加载基线不补发历史、同一条告警只通知一次、权限拒绝时静默跳过、不支持环境返回 `unsupported`、发送异常不抛出
- [x] 2.3 实现 `lastSeenAlertId` 基线 + `notifiedAlertIds` 去重逻辑(基线 = 首次成功轮询响应中的最新未读 id),随 2.2 测试先行通过

## 3. 轮询与可见性

- [x] 3.1 修改 `frontend/src/utils/poller.js`:隐藏状态下轮询频率降为 `max(60s, interval × 2)` 且仍执行回调;新增 `onVisibilityVisible` 钩子,`visibilitychange` 转可见时立即触发一次刷新
- [x] 3.2 更新 `frontend/tests/poller.test.js`:mock `document.visibilityState` 与 interval,断言隐藏降频、恢复可见立即回调、频率不高于前台
- [x] 3.3 在 `frontend/src/App.vue` 接线:现有告警轮询回调中比较最新未读 id 并触发 `sendTriggerNotification`;`/api/alerts/count` 结果同步到 `document.title` 徽标(未读为零恢复原标题)
- [x] 3.4 在 `frontend/src/App.vue` 注册 `visibilitychange` 监听 → 可见时立即刷新告警与当前页面数据,卸载时清理监听

## 4. 设置页通知区

- [x] 4.1 `frontend/src/stores/runtimeCapabilities.js` 兜底 `browser_notifications: false`,与后端契约合并后作为设置区可见性门控
- [x] 4.2 `frontend/src/views/Settings.vue` 新增"触发通知"区:通知开关(开启时在用户手势中 `ensurePermission()`)、声音开关(默认关闭)、权限状态展示(已授予/被拒绝/不支持)与拒绝时"通过浏览器站点设置重新授权"指引;区内容受能力门控,能力不可用时隐藏
- [x] 4.3 偏好持久化到 localStorage,读取时以 `Notification.permission` 实际状态修正显示
- [x] 4.4 更新/新增挂载测试(`frontend/tests/notifications.mount.spec.js`):开启开关才调用权限请求、权限拒绝时显示指引且不崩溃、能力隐藏时不渲染通知区

## 5. 测试翻转与 E2E

- [x] 5.1 翻转 `frontend/tests/notification-permission.test.js`:原"页面加载不请求权限"断言保留,新增"显式开启通知时才请求权限"断言,更新测试名与说明以反映新语义
- [x] 5.2 在 `frontend/tests/e2e/supported-runtime.spec.js` 增加通知场景:`addInitScript` 注入 Notification stub 记录到 `window.__notifications`;两态断言——权限已授予时新触发创建通知,权限拒绝时不创建通知且未读徽标仍在
- [x] 5.3 运行前端全量测试与 `npm run build`,确认包体预算通过

## 6. 文档与门禁

- [x] 6.1 更新 README"受支持运行面"表格:浏览器系统通知行从"推迟,不在稳定 UI 显示"改为"支持(站内呈现,仅本机)";Webhook 行保持推迟;补充通知权限与降级行为说明
- [x] 6.2 更新 CLAUDE.md(如设计规则涉及通知边界)与 `openspec/platform-evolution-roadmap.md`(notification-delivery 域状态)
- [x] 6.3 运行 `.\verify.ps1` 全量门禁,确认后端测试、前端测试、构建、E2E、smoke、恢复演练与 OpenSpec 严格校验全部通过
- [x] 6.4 归档本 change(`/opsx:archive`)前,同步 delta specs 到主 specs(`/opsx:sync`)
