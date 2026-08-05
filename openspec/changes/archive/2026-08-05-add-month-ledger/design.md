# Design — 本月账本：仪表盘月度盈亏与纪律统计

## Context

- `backend/routers/dashboard.py::get_dashboard` 目前内联计算全量聚合：`realized = Σ(close_price − buy_price) × quantity`（全生命周期）、当前浮亏、状态计数、今日告警。月界先例：今日告警用 `ZoneInfo(config.timezone)` 把上海日界转成 naive UTC 后与 SQLite 时间戳比较。
- `Holding` 无 `closed_at` 列；closed 持仓不可再修改（400），因此 `updated_at` 在平仓后冻结，可作为平仓时间归属（精度足够，文档注明）。
- `stop_rule_history` 自包含快照（含 `stop_loss_price`、`source` ∈ create/update/rearm、`changed_at`），可做"调低止损"方向判定。
- 每条 `Alert` 记录 = 一次触发生命周期（rearm 产生新告警），本月触发数 = 本月 `created_at` 的告警数。
- 前端 `Dashboard.vue` 用 `emptyDashboard` 对象作默认值，`dashboard.value = res.data` 整体替换；卡片展示需在默认值中给 `month_summary` 提供安全缺省。
- 约束：无 schema 变更/迁移；不新增端点；沿用 dashboard 现有 float 金额口径（与 risk 的 str 口径不同，属既有模块惯例）；测试离线（网络哨兵）；月份标签与时段徽标同为 Asia/Shanghai。

## Goals / Non-Goals

**Goals:**
- 仪表盘响应携带 `month_summary`，覆盖本月已实现盈亏、平仓笔数、触发数、止损调整/调低次数、最大浮亏来源。
- 前端首屏"本月账本"卡片：一个主导数字 + 辅助行 + 行动出口，空组合零值，向后兼容。
- 全部聚合在既有 `/api/dashboard` 请求内完成，**不新增网络请求**。

**Non-Goals:**
- 不做月度报告页面/导出、不做趋势图、不做桌面通知、不改动止损逻辑。
- 不新增 `closed_at` 列（无迁移）；平仓时间以冻结的 `updated_at` 为准。
- 不计算历史月份（`month_summary` 只描述当前月；历史聚合留给后续报告 change）。
- 不把已实现与浮亏合并成单一"账户变动"数字（避免语义造假）。

## Decisions

### D1: 聚合位置 — 内联在 `get_dashboard`（沿用模块风格）
- dashboard 模块现有全部聚合内联在 router 中，无 service 层；`month_summary` 同样内联，保持模块一致性。
- 备选：抽取 `services/ledger.py`——被拒：单一调用方、无复用诉求，提前抽象违背本模块现状；若后续月度报告 change 需要按年/月参数化，再抽取不迟。

### D2: 月界 — Asia/Shanghai，naive UTC 比较（复用今日告警模式）
- `month_start` = 本月 1 日 00:00（上海）→ UTC naive；`next_start` = 下月 1 日 → UTC naive；所有比较用 `>= month_start and < next_start`。
- `month` 标签 = `today.strftime("%Y-%m")`（上海时区）。

### D3: 本月已实现盈亏与平仓笔数
- 过滤 `status == "closed"`、`close_price is not null`、`updated_at` 落在月界内的持仓：`realized = Σ(close − buy) × quantity`（Decimal 计算，与现有一致），`closed_count` = 行数。
- 精度说明：无 `closed_at` 列，`updated_at` 在平仓后冻结，故等价于平仓时间；代码注释注明。

### D4: 触发与止损调整统计
- `triggered_count`：`Alert.created_at` 落在月界内的行数。
- `stop_adjustment_count`：`StopRuleHistory.changed_at` 落在月界内且 `source in ("update", "rearm")` 的行数。
- `stop_lowered_count`：在调整行中，按 `(holding_id, changed_at, id)` 排序后，与**同一持仓上一条历史记录**（任意 source，create 为基线）比较，当前 `stop_loss_price < 上一条` 的计数。无上一条（如月份内第一条历史即 create）不计入调低。

### D5: 最大浮亏来源
- 在可估值的当前持仓（`status in ("holding","triggered")`、`quote_state != "unpriced"`、`current_price` 非空）中取 `(current_price − buy_price) × quantity` 最小者；若最小者 ≥ 0（无浮亏）或无可估值持仓 → `largest_loss = null`。
- 字段：`{name, code, profit_loss_amount}`（负数 float）。

### D6: Schema 与响应契约
- `schemas.py` 新增 `LargestLoss(BaseModel)` 与 `MonthSummary(BaseModel)`；`DashboardResponse` 增加必填字段 `month_summary: MonthSummary`。
- 金额用 float（与 dashboard 现有字段一致）；空组合返回全零计数 + `realized_profit_loss: 0.0` + `largest_loss: null`（与"空组合显示零值"的 dashboard 规范一致，不返回 null 聚合）。
- 旧字段全部保持不变 → 旧前端兼容。

### D7: 前端"本月账本"卡片
- 位置：仪表盘"行情可信/覆盖"摘要之后、待处置队列之前（风险优先布局：先信任、后组合风险、再行动）。
- 主导数字：`month_summary.realized_profit_loss`（`formatMoney` 显示，`tone-profit/tone-loss` 着色），副标题"平仓 N 笔"。
- 辅助行：本月触发 N 次 · 调整止损 N 次（调低 M）；当前浮亏（复用既有 `unrealized_profit_loss`，注明是快照）；`largest_loss` 非空时显示"最大亏损来源：名称 ¥X"。
- 行动出口：待处置数 > 0 时显示"去处置"按钮（路由 `/alerts`）；否则显示"无待处置"弱化文案。
- `emptyDashboard` 增加 `month_summary: null` 缺省；模板 `v-if="dashboard.month_summary"` 守卫，旧数据/加载中不渲染卡片。
- 样式沿用既有 panel/卡片变量（`--color-surface`、`--color-profit/loss`、`risk-*`），响应式单列。

### D8: 测试策略
- 后端契约测试（新增 `backend/tests/test_month_ledger.py`，沿用内存库 bootstrap）：直接以 session 造数控制时间戳——
  - 本月/上月 closed 持仓各一笔 → 只统计本月；`updated_at` 冻结语义断言
  - 本月/上月告警 → `triggered_count` 只含本月
  - 历史记录方向：调低一次、调高一次、rearm 一次 → `stop_adjustment_count = 2`（update+rearm）、`stop_lowered_count` 按方向正确；月份内第一条 create 不计入调整
  - 空组合 → 全零 + `largest_loss: null`；全部浮盈 → `largest_loss: null`
  - `month` 标签为 `YYYY-MM`；`DashboardResponse` 序列化含新字段
- 前端 mount 测试（`dashboard` 相关现有 mount spec 或新增）：mock api 返回含 `month_summary` 的 payload → 卡片渲染主导数字/行/待处置按钮；`month_summary: null` 时不渲染；空值零值显示。
- E2E：新场景或扩展既有仪表盘场景——seed 一笔持仓并走真实平仓流程（close），`page.request.get('/api/dashboard')` 取 `month_summary.realized_profit_loss`，断言卡片文本与 API 值一致（用唯一持仓名，不断言绝对值，规避共享 e2e.db 累积）。
- 页面完整性：`assertPageIntegrity`（无横向滚动/无控制台错误）在三个视口继续通过。

## Risks / Trade-offs

- [`updated_at` 作为平仓时间：若未来引入"closed 后更新"逻辑会破坏归属] → 现状 closed 不可写（400 门禁），契约测试断言冻结语义；若未来改变，测试先行暴露。
- [调低方向判定依赖历史记录存在（create 基线）] → 无上一条不计入调低；测试覆盖"月份从 create 开始"的边界。
- [浮亏与已实现同屏可能被误读为合计] → 卡片文案明确区分"已实现（本月）"与"浮亏（当前快照）"，不合并展示。
- [共享 e2e.db 使绝对数值断言脆弱] → E2E 只断言"卡片展示值 == API 值"，不断言具体金额。
- [DashboardResponse 新增必填字段：旧前端忽略未知字段] → 纯增量，FastAPI 序列化向后兼容。

## Migration Plan

- 无数据库迁移。后端字段纯增量；前端随构建同仓发布。
- 回滚：还原代码即可；旧前端忽略 `month_summary`，新前端对缺失字段有 `v-if` 守卫。

## Open Questions

- 无阻塞性问题。`stop_lowered_count` 的"调低"以绝对价比较（非百分比），对固定/百分比/移动三种方式均适用，无需区分方式。
