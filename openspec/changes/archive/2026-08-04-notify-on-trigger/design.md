## Context

现状:前端轮询(`src/utils/poller.js`)在 `visibilityState === 'hidden'` 时完全跳过回调;App.vue 每 30s(可配置)轮询 `/api/alerts?unread=true&size=1` 与 `/api/alerts/count`,新触发只以站内 `ElNotification` 呈现。无浏览器通知、无声音、无 title 徽标。`tests/notification-permission.test.js` 明确断言"页面不请求通知权限"——这是旧 `notification-delivery` 边界(浏览器通知无 owner)在测试层的固化,本 change 将翻转该语义。

后端能力契约(`services/supported_runtime.py` 的 `RuntimeCapabilities`)目前只有 `webhook_delivery: bool = False`,不存在浏览器通知字段。`frontend-shell` spec 要求"遵循服务端声明的运行时能力",因此通知设置区的可见性必须由后端能力字段驱动,而不是前端写死。

边界约束:本地单用户、loopback、不新增后端 API 调用面、站内告警仍是唯一通知事实、测试保持离线 hermetic。

## Goals / Non-Goals

**Goals:**
- 新触发告警在标签页隐藏时仍被检测,并通过浏览器通知/声音/title 徽标到达用户。
- 恢复可见时立即刷新,消除最长一个轮询周期的陈旧数据窗口。
- 通知权限只在用户显式开启时请求,页面加载零特权请求。
- 权限被拒/不支持时优雅降级,核心流程不受影响。

**Non-Goals:**
- 不实现 Webhook、Service Worker 推送、跨设备投递或任何外部通道。
- 不改后端站内告警 API(`/api/alerts` 契约不变),不新增轮询端点。
- 不做桌面托盘/常驻后台程序(浏览器通知依赖页面上下文存活)。
- 不改变前台轮询频率与现有设置项行为。

## Decisions

### D1:隐藏时降频轮询,而非 Web Worker 常驻轮询
`poller.js` 增加隐藏策略:隐藏期间频率 = `max(60s, pollInterval × 2)`,可见时恢复原频率。**备选**:Web Worker 独立轮询 + `postMessage` 桥接——worker 无法共享 Vue 响应式状态,需要复制告警 API 调用与基线逻辑,单机单标签场景收益不抵复杂度;浏览器对隐藏标签的 setInterval 节流(~1/min,Chrome)恰好与 60s 目标对齐,降频方案不需要对抗平台行为。注意:通知发送必须保持在主线程(Web Notification API 在主线程即可用,不依赖 worker)。

### D2:通知触发 = 现有轮询回调内的"新未读告警 id"比较
App.vue 已在轮询 `/api/alerts?unread=true&size=1`。设计:维护 `lastSeenAlertId`(加载基线 = 首次成功响应中的最新未读 id)与 `notifiedAlertIds`(去重集合);每次轮询若最新未读 id 不在集合且晚于基线 → 发送通知并记录。**备选**:后端新增 `since` 参数或事件端点——改变 API 契约,违背 Non-Goals;现有接口已含全部所需信息。标记全部已读后基线自然重置(未读为空),不会误报。

### D3:通知开关存 localStorage,不进后端 settings
通知偏好是浏览器/设备级状态,与后端运行面设置(轮询间隔等)性质不同;存后端会造成"浏览器拒绝权限但服务端声明已启用"的口径分裂,且引入新 API。**备选**:进后端 settings 表——需要迁移与接口变更,收益为零。风险:多浏览器(localhost)各存一份,单机单用户场景可接受。读取时以 `Notification.permission` 实际状态为准修正显示。

### D4:声音用 Web Audio 振荡器,不打包音频资源
短促的双音提示,默认关闭。**备选**:打包音频文件——增加资源与包体预算压力,且 `verify.ps1` 的 bundle 预算检查会受影响;振荡器零资源、零网络,音量跟随系统。仅作为通知的补充,不与通知解耦(声音开关独立于通知开关,但默认都关)。

### D5:后端新增 `browser_notifications` 能力字段
`RuntimeCapabilities` 增加 `browser_notifications: bool = False` 默认值,legacy 与 shadow-read 策略声明为 True;前端 `CLOSED_CAPABILITIES` 兜底 `browser_notifications: false`,运行时契约合并后驱动设置页通知区可见性。理由:遵循既有"能力由服务端裁决"架构(frontend-shell spec),Webhook 字段维持 False 不变。

### D6:title 徽标与铃铛角标共享同一未读计数
App.vue 已轮询 `/api/alerts/count`,title 徽标直接复用该值(`document.title = "(3) 止损不止盈"`,未读为零时恢复原标题),不新增第二个请求源。铃铛角标逻辑不动,避免双口径。

### D7:测试策略(保持 hermetic)
- **单测(node:test)**:`notifications.js` 纯逻辑——权限状态机(已授予/拒绝/不支持)、通知内容构造、去重基线(加载不补发)、发送失败静默;`poller.js` 隐藏降频与 visibilitychange 立即刷新(注入 mock document)。
- **挂载(vitest)**:App.vue 新触发→通知创建调用;Settings.vue 开关交互(开启才请求权限)。
- **翻转 `notification-permission.test.js`**:断言"页面加载不请求权限、显式开启才请求"。
- **E2E(Playwright)**:`addInitScript` 注入 Notification stub 记录到 `window.__notifications`,两态断言(授权→创建通知;拒绝→降级无通知、徽标仍在);后台节流属真实浏览器行为,轮询频率逻辑不依赖 E2E。

## Risks / Trade-offs

- [隐藏标签的浏览器计时节流可能让降频轮询实际更慢(Chrome 约 1/min)] → 60s 目标频率与节流节奏对齐,文档说明通知可能存在分钟级延迟;下限优于现状(零检测)。若轮询被完全挂起,恢复可见时的立即刷新兜底。
- [权限被用户永久拒绝] → 设置页显示拒绝状态与"通过浏览器站点设置重新授权"指引;title 徽标与声音仍可用;核心流程不受影响。
- [`notification-permission.test.js` 语义翻转遗漏导致 verify 红] → 该测试列入本 change 的必改清单,与前端实现同批提交。
- [通知与铃铛角标计数口径分裂] → D6 强制单事实来源;spec 场景显式断言一致。
- [E2E 中 Notification 权限不可真实授予] → Playwright stub 方案(而非真实权限),离线断言行为而非浏览器能力。
- [localStorage 偏好与浏览器权限状态不同步(用户手动在浏览器设置撤销权限)] → 每次发送前检查 `Notification.permission`,不为 granted 时静默跳过并更新设置页状态。

## Migration Plan

无数据库迁移、无 API 契约变更。部署 = 前端 bundle + 后端能力字段同版发布:
1. 后端新增能力字段与测试,verify 门禁通过。
2. 前端实现 + 测试翻转,verify 门禁通过。
3. README 受支持运行面表格更新("浏览器系统通知"行从推迟改为支持,Webhook 行保持推迟)。
4. 回滚:整体 revert 前端 bundle 与后端字段即可;localStorage 残留键被旧版本忽略,不破坏旧版运行。

## Open Questions

- 隐藏轮询频率是否需要跟随用户可配置的 pollInterval 联动(现设计 `max(60s, interval×2)` 已隐含联动)?——实施时以单测固化该公式即可,无需产品决策。
