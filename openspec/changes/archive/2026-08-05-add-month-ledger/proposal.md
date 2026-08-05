# 本月账本：仪表盘月度盈亏与纪律统计

## Why

用户的核心痛点是"一直亏但没算过账，反应过来时已经亏了很多"。现有仪表盘只展示**全生命周期快照**（累计已实现盈亏、当前浮亏），没有时间维度——回答不了"这个月到底亏了多少、怎么亏的"。而所需数据全部已持久化（closed 持仓的成本/平仓价/数量、告警时间线、`stop_rule_history`），本 change 让工具**自动持续算账**：打开仪表盘第一眼就是本月数字，为后续月度报告打基础。

## What Changes

- `GET /api/dashboard` 响应新增 `month_summary` 字段（向后兼容的纯增量，缺省行为与旧字段不变）：
  - `month`：当前月份标签（`YYYY-MM`，Asia/Shanghai 月界）
  - `realized_profit_loss` / `closed_count`：**本月**已实现盈亏与平仓笔数（按 closed 持仓的平仓时间归属，`close_price - buy_price × quantity`）
  - `triggered_count`：本月触发告警数（每条告警 = 一次触发生命周期）
  - `stop_adjustment_count` / `stop_lowered_count`：本月止损调整总次数与其中**调低**止损的次数（`stop_rule_history` 来源 `update`/`rearm`，方向按同一持仓相邻历史记录比较）
  - `largest_loss`：当前最大浮亏来源（名称/代码/浮亏额）或 `null`（无可行动浮亏持仓）
- 前端仪表盘首屏新增"本月账本"卡片：主导数字为**本月已实现盈亏**（盈亏色），辅助行展示平仓笔数、触发/调整次数、当前浮亏参考、待处置行动入口；月份标签与现有时段徽标同一时区口径；空组合显示零值。
- 配套测试：后端契约测试（月界归属、方向统计、空组合、最大浮亏可空）、前端 mount 测试（卡片渲染与数值展示）、E2E（卡片展示值与 API 一致）。
- README 仪表盘章节补充"本月账本"说明。

## Capabilities

### New Capabilities

（无——本 change 不引入新运行面能力）

### Modified Capabilities

- `dashboard`: 仪表盘数据契约新增 `month_summary` 月度聚合；前端新增"本月账本"卡片与行动出口

## Impact

- API: `backend/routers/dashboard.py`（`get_dashboard` 内联聚合，沿用模块现有风格）、`backend/schemas.py`（新增 `MonthSummary`/`LargestLoss`，`DashboardResponse` 增加字段）
- 前端: `frontend/src/views/Dashboard.vue`（`emptyDashboard` 默认值 + 卡片模板与样式）
- 测试: `backend/tests/`（新增月度聚合契约测试）、`frontend/tests/`（mount 测试）、`frontend/tests/e2e/supported-runtime.spec.js`（数值一致性场景）
- 文档: `README.md`（仪表盘章节）
- 无数据库 schema 变更、无迁移、无新端点。
