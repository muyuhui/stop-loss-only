## Why

止损监控工具的信任建立在"数据是否新鲜、规则是否可追溯"之上。当前存在三个产品级缺口：①设置页开了通知开关后无法立即验证管道是否可用，只能等真实触发；②后端已经算出交易时段（`market_clock.market_session`），UI 却从不呈现，用户无法一眼判断"现在是盘中还是休市、行情是什么时候的"；③README 明确承认"历史止损线按当前止损配置计算，不代表过去真实配置记录"——用户修改止损后，无法追溯每次调整，图表也无法画出触发时刻的真实止损线。三项都是低成本、直击信任感的改进。

## What Changes

- **测试通知**：设置页"触发通知"区新增"发送测试通知"按钮，在用户手势中直接发送一条样本浏览器通知（可同步播放提示音验证声音），不产生业务事实、不写告警表；权限被拒时复用现有重新授权指引，不阻塞。
- **交易时段指示**：`GET /api/monitoring/status` 响应新增 `market_session`（`pre_market`/`open`/`lunch`/`closed`），前端在仪表盘与设置诊断区展示"交易中/午休/已收盘/盘前"徽标；时段为时间语义，不判定节假日（与现状一致，文档说明）。
- **行情时效指示**：持仓卡片与仪表盘展示每条行情的新鲜度（`quoted_at` 距今分钟数或"已收盘"），未定价/无行情时不显示虚假时效。
- **止损调整历史**：新增 `stop_rule_history` 表（迁移 revision 8）记录每次止损规则写入（创建时的初始规则、修改时的规则变化，含方法、值、计算后的止损价、时间）；`GET /api/holdings/{id}` 与列表响应附带最近历史，详情页新增"止损调整记录"时间线；图表历史止损线口径不变（仍按当前配置），README 的免责说明改为指向可查询的历史记录。

## Capabilities

### New Capabilities

（无新增能力——三项均为既有域的增强）

### Modified Capabilities

- `notification-delivery`: 新增"测试通知"呈现路径——用户显式触发一条样本通知验证管道，不创建告警事实。
- `monitoring-diagnostics`: `market_session` 进入运行时状态契约；前端可据此呈现交易时段。
- `holdings-crud`: 止损规则调整须记录可查询的历史（创建与每次修改），持仓/列表响应暴露时效字段；不改变规则语义与生命周期。
- `dashboard`: 仪表盘呈现交易时段与行情时效，不改变聚合口径。

## Impact

- **后端**（中）：`migrations.py` 新增 revision 8（`stop_rule_history` 表）；`models.py`、`routers/holdings.py`（创建/修改时写入历史 + 读取端点）、`schemas.py`（历史与状态字段）、`routers/monitoring.py`（`market_session`）、`services/market_clock.py` 无改动（已有 `market_session`）。
- **前端**（中）：`Settings.vue`（测试通知按钮）、`Dashboard.vue` 与持仓卡片（时段徽标、行情时效）、`HoldingDetail.vue`（止损调整时间线）、`src/api`（新端点）。
- **测试**：后端历史写入/查询/迁移幂等测试、监控状态契约测试；前端挂载测试与 E2E（测试通知两态、时段徽标、历史时间线）。
- **文档**：README（止损历史免责说明更新、时段/时效说明）。
- **风险与边界**：不改变止损规则计算、不改变告警事实来源、不引入外部日历；`stop_rule_history` 只读不回放，删除持仓后历史保留（与告警快照保留口径一致）。
