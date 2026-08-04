## Context

三项独立的小改进，共享同一个动机：让"止损监控"的信任可验证。现状：

- 通知管道（`frontend/src/utils/notifications.js` + 设置页开关）刚上线，但没有自检入口——用户开了开关后只能等真实触发才知道是否生效。
- 后端 `services/market_clock.py` 已有 `market_session()`（`pre_market`/`open`/`lunch`/`closed`），但任何 UI 都不消费它；`Holding.quoted_at` 已随 `HoldingResponse` 与 dashboard 载荷下发，前端也未呈现时效。
- 止损规则写入点只有两处：`POST /api/holdings`（创建初始规则）与 `PUT /api/holdings/{id}`（修改）；README 明确说明"历史止损线按当前止损配置计算，不代表过去真实配置记录"。

约束：本地单用户 loopback、Decimal 金融计算、迁移幂等可重入、测试 hermetic、运行时能力契约不变（三项均为既有域增强，不新增能力开关）。

## Goals / Non-Goals

**Goals:**
- 设置页可一键发送测试浏览器通知（含提示音），验证整条管道，不产生业务事实。
- 运行时状态呈现交易时段；持仓/仪表盘呈现行情时效，未定价等无行情状态绝不显示虚假时效。
- 每次止损规则写入（创建 + 修改）落一条可查询的历史记录；详情页展示时间线；删除持仓后历史保留（与告警快照口径一致）。
- 全部通过既有 `verify.ps1` 门禁。

**Non-Goals:**
- 不改变止损规则计算与告警事实来源（历史记录只读不回放）。
- 图表历史止损线仍按当前配置计算；用历史数据重绘"当时的线"留作后续 change。
- 不引入节假日/周末日历（`market_session` 保持现有时间语义，文档注明）。
- 不实现 `stop_rule_history` 的编辑、回滚或 retention 清理（本地单用户，保留全部）。

## Decisions

### D1: 止损历史 = 快照行 + 创建/修改双写入钩子
`stop_rule_history` 每行自包含快照：`holding_id`、`code`、`name`、`stop_loss_method`、`stop_loss_value`、`stop_loss_price`、`source`（`create`/`update`）、`changed_at`。写入点：
- `create_holding` 成功后写 `source='create'`；
- `update_holding` 仅在止损字段实际变化时写 `source='update'`（比较 `prospective_*` 与当前值，不变则跳过），且在同一个 `_commit_legacy` 事务内。
**备选**：只记修改不记创建（丢失基线）；全表快照审计（超出需求）；存 JSON 到 settings（非结构化，无法按持仓查询）。选择快照行的理由：自包含、可随持仓删除保留、与告警快照的哲学一致。表结构由模型元数据创建（`create_all` 幂等），显式索引 `ix_stop_rule_history_holding`；`LATEST_SCHEMA_VERSION` 升到 8，`downgrade` 按既有非破坏语义只删版本行。

### D2: `market_session` 放进 `/api/monitoring/status`
该端点已是运行时状态的事实来源（调度、下次运行、行情新鲜度原因码），前端 Settings 诊断区已在轮询。响应增加 `market_session: "pre_market" | "open" | "lunch" | "closed"`，由 `market_clock.market_session()` 生成。**备选**：新建 `/api/market/session`（新增调用面，违背最小暴露）；前端本地算（节假日/时区口径与后端分裂）。前端映射：盘前/交易中/午休/已收盘；Dashboard 顶部徽标 + Settings 诊断行展示。不判定周末与节假日——与 `market_clock` 现状一致，README 注明。

### D3: 行情时效由前端基于 `quoted_at` 计算
`HoldingResponse` 已携带 `quoted_at`（`schemas.py`），前端用本地时钟计算年龄：`<60s` 显示"刚刚"，`<60min` 显示"N 分钟前"，更早显示本地时间；`quote_state` 为 `unpriced`/`error` 时不显示时效（显示"未定价/行情不可用"）。**备选**：后端计算 `quote_age_minutes` 字段（增加 schema 面；本地单机时钟漂移可忽略）。持仓卡片与仪表盘共用同一 `formatQuoteFreshness` 工具函数，口径单一。

### D4: 测试通知 = `sendTestNotification()`，独立于告警发送
`notifications.js` 新增 `sendTestNotification({ playSound })`：构造固定样本内容（标题"止损不止盈测试通知"，正文含示例持仓快照文字），`tag: 'test'`，点击无跳转；发送前同样校验 `Notification.permission`；`playSound` 时走 `playTriggerChime()`。设置页按钮仅在权限 `granted` 时可用；`default`/`denied` 时点击给出提示（"请先开启系统通知"或既有重新授权指引），绝不自动请求权限。**备选**：复用 `sendTriggerNotification` 传假告警——会把测试内容误入通知去重/基线语义，且需要假 `holding_id`；独立函数更干净。测试通知不调用任何 API，不写任何表。

### D5: 历史保留口径 = 随持仓删除保留
`delete_holding` 不级联删除 `stop_rule_history`（与"历史告警快照不会被删除"一致）；快照行自包含 `code`/`name`，删除后仍可审计。不设外键级联，`holding_id` 仅作查询键。

## Risks / Trade-offs

- [测试通知内容与真实触发混淆] → 标题明确"测试"字样，`tag: 'test'` 使新测试通知替换旧测试通知，不进入告警去重集合。
- [`market_session` 与真实休市日不符（节假日显示"交易中"）] → 与既有 `market_clock` 语义一致（价格可信度已由 `WEEKDAY_FALLBACK` 等机制约束触发），README 明示"时段指示不判定节假日"。
- [前端本地时钟与 `quoted_at` 服务器时间漂移] → 单机本地场景可忽略；显示粒度到分钟，不做秒级断言。
- [历史表无限增长] → 本地单用户写入频率极低（每次止损修改一行），不做 retention；README 提示可手动清理。
- [迁移 8 对旧库升级] → `create_all` 幂等创建缺失表 + 显式索引；升级/降级演练纳入 verify 门禁。

## Migration Plan

1. 后端：模型 + `LATEST_SCHEMA_VERSION=8` + 写入钩子 + 查询端点 + 状态字段，后端测试通过。
2. 前端：测试通知按钮、时段/时效工具与展示、详情页时间线，前端测试 + 构建通过。
3. 文档：README 免责说明更新为指向历史记录；时段/时效说明。
4. 回滚：整体 revert 前端 bundle 与后端代码即可；`stop_rule_history` 表在降级后保留（非破坏，旧代码忽略）。

## Open Questions

- 详情页时间线是否需要"按时间回放止损价"的图表叠加（在某一时间点止损是多少）？——非本 change 目标，留作后续（图表免责说明将指向历史记录）。
