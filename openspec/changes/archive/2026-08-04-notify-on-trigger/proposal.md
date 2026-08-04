## Why

当前稳定版本存在一个产品级缺口:前端轮询在标签页隐藏时完全暂停(`frontend/src/utils/poller.js:7`),且没有任何浏览器通知、声音或未读徽标。用户切到其他标签页后,止损触发完全静默,直到回到页面等待下一个周期才可见。作为"止损监控"工具,触发事实无法在用户不注视页面时到达用户。`notification-delivery` spec 拒绝浏览器通知的理由是"缺少完整运行时 owner";本次 change 为该通道补齐 owner(运行中的前端浏览器上下文),并在不扩大外部投递边界的前提下恢复此能力。

## What Changes

- **浏览器系统通知**:新触发告警时通过 `Notification` API 呈现站内告警事实(标题、持仓名/代码快照、当前价与止损价、处置入口)。通知只是站内告警的呈现,不产生新事实,不依赖外部投递成功。
- **后台轮询**:标签页隐藏时不再完全暂停,降频保持告警轮询(`/api/alerts?unread=true`),使隐藏状态下的新触发仍能被检测并通知。恢复可见时立即刷新,不等下一个周期。
- **未读表达**:`document.title` 显示未读告警徽标;移动端底部导航/桌面铃铛的未读角标与现有告警计数保持一致。
- **声音提示**:新触发时可选播放提示音(默认关闭,设置页开关)。
- **设置页通知区**:显式开关(通知总开关、声音开关)、权限状态展示(已授予/被拒绝/不支持)与"检测权限"说明。权限请求只在用户显式开启时发起(用户手势),页面加载绝不主动请求。
- **运行时能力契约**:后端 `RuntimeCapabilities` 新增 `browser_notifications` 字段,legacy 与 shadow-read 阶段声明为 true;前端据此决定是否展示通知设置区。Webhook 通道维持拒绝,不进入本 change。
- **测试翻转**:`frontend/tests/notification-permission.test.js` 当前断言"页面不请求通知权限"(旧的有意排除),本次变更为"权限只在用户显式开启时请求";新增后台轮询、徽标、通知内容与降级路径的单元/挂载测试,E2E 使用 Playwright 的权限 mock 保持离线。

## Capabilities

### New Capabilities

(无新增能力——本 change 激活既有 `notification-delivery` 域中的浏览器通知通道,并调整 `frontend-shell` 的特权请求与轮询行为)

### Modified Capabilities

- `notification-delivery`:浏览器系统通知从"稳定版本默认拒绝"变为"受支持的前端投递路径"(owner = 运行中的前端浏览器上下文);Webhook 仍保持拒绝;站内告警仍是唯一通知事实,浏览器通知只呈现该事实。
- `frontend-shell`:更新"Request privileged capabilities on demand"要求——系统通知权限从绝对禁止请求改为"仅在用户显式开启通知时按需请求";并补充后台轮询降频、可见性恢复刷新与未读徽标的表达要求。

## Impact

- **前端**(主要):`src/utils/poller.js`(隐藏降频策略)、`src/App.vue`(通知触发、title 徽标、visibilitychange 刷新)、新增 `src/utils/notifications.js`(权限与发送封装)、`src/views/Settings.vue` 与 `src/stores/settings.js`(通知设置区)、`src/stores/runtimeCapabilities.js`(消费 `browser_notifications` 能力)、`src/styles.css`(徽标样式)。
- **后端**(小):`services/supported_runtime.py` 的 `RuntimeCapabilities` 新增 `browser_notifications` 字段并声明为 true;对应受支持运行时测试补充。无数据库迁移,无站内告警 API 契约变化。
- **测试**:翻转 `notification-permission.test.js` 语义;新增后台轮询/徽标/通知内容/降级路径单测与挂载测试;Playwright E2E 增加通知 mock(权限已授予与已拒绝两态)。
- **文档**:README 受支持运行面表格(浏览器通知行从"推迟/不在稳定 UI 显示"改为"支持");`notification-delivery` 与 `frontend-shell` spec 增量;CLAUDE.md 设计规则如涉及通知边界一并更新。
- **风险与边界**:不引入认证或公网暴露;通知仅本机浏览器呈现;权限被拒或环境不支持时降级为 title 徽标 + 声音,不破坏核心流程;隐藏轮询必须限制频率并遵守既有告警轮询接口,不新增后端调用面。
