## 1. 止损历史（后端）

- [x] 1.1 `models.py` 新增 `StopRuleHistory` 模型（holding_id/code/name/stop_loss_method/stop_loss_value/stop_loss_price/source/changed_at），`migrations.py` 的 `LATEST_SCHEMA_VERSION` 升到 8，显式创建 `ix_stop_rule_history_holding` 索引
- [x] 1.2 `routers/holdings.py`：`create_holding` 与 `_commit_legacy` 同一事务内写 `source='create'` 历史行；`update_holding` 仅在止损字段实际变化时写 `source='update'` 历史行
- [x] 1.3 新增 `GET /api/holdings/{id}/stop-history`（按 `changed_at`/`id` 倒序），`schemas.py` 定义响应模型
- [x] 1.4 补充后端测试：创建写初始历史、修改写变更、无变化不写、查询倒序、删除持仓后历史保留、v7→v8 升级幂等与降级演练

## 2. 止损历史（前端）

- [x] 2.1 `HoldingDetail.vue` 新增"止损调整记录"时间线区块（来源 create/update、方式/参数/止损价、时间），通过 `GET /api/holdings/{id}/stop-history` 加载
- [x] 2.2 补充挂载测试：时间线渲染、空历史空状态、加载失败降级且不崩溃

## 3. 交易时段与行情时效（后端）

- [x] 3.1 `routers/monitoring.py` 状态响应增加 `market_session`（复用 `services/market_clock.market_session()`），`schemas.py` 状态模型补字段
- [x] 3.2 后端测试：`pre_market`/`open`/`lunch`/`closed` 映射与既有状态字段不变断言

## 4. 交易时段与行情时效（前端）

- [x] 4.1 新建 `frontend/src/utils/market.js`：`formatMarketSession(session)`（盘前/交易中/午休/已收盘）与 `formatQuoteFreshness(quotedAt)`（刚刚/N 分钟前/本地时间/不可用），未定价不显示时效
- [x] 4.2 `Dashboard.vue`：监控状态区展示时段徽标（请求失败或字段缺失时降级不显示）；持仓概览卡片展示行情时效
- [x] 4.3 `Holdings.vue` 卡片与 `HoldingDetail.vue` 摘要区展示行情时效，未定价显示"未定价/行情不可用"
- [x] 4.4 前端测试：时段映射、时效文本边界（<60s、<60min、更早、null）、仪表盘时段徽标挂载测试

## 5. 测试通知

- [x] 5.1 `frontend/src/utils/notifications.js` 新增 `sendTestNotification({ playSound })`：样本内容 + 标题含"测试" + `tag: 'test'` + 点击无副作用 + 发送前校验 `Notification.permission`；`playSound` 时播放 `playTriggerChime()`
- [x] 5.2 `Settings.vue`"触发通知"区新增"发送测试通知"按钮：仅 `granted` 时发送；`default`/`denied` 点击给出"请先开启系统通知"或既有重新授权指引，不自动请求权限；声音开关开启时同步播放提示音
- [x] 5.3 更新 `frontend/tests/notifications.test.js`（测试通知内容/tag/权限校验/异常静默/点击无副作用）与 `frontend/tests/notifications.mount.spec.js`（granted 发送、denied 提示且不发送）
- [x] 5.4 E2E（`frontend/tests/e2e/supported-runtime.spec.js`）：设置页点击测试通知 → stub 记录一条 `tag='test'` 通知且无业务 API 写入；权限拒绝态点击不创建且显示提示

## 6. 文档与门禁

- [x] 6.1 更新 README：历史止损线免责说明改为指向 `stop_rule_history` 可查询记录；交易时段指示（不判定节假日）与行情时效说明
- [x] 6.2 运行 `.\verify.ps1` 全量门禁，确认后端测试、前端测试、构建、E2E、smoke、恢复演练与 OpenSpec 严格校验全部通过
- [x] 6.3 归档本 change 前，同步 delta specs 到主 specs（`/opsx:sync`），再归档（`/opsx:archive`）
