## ADDED Requirements

### Requirement: 返回本月账本聚合
`GET /api/dashboard` SHALL 在响应中返回 `month_summary` 聚合，包含：`month`（当前月份标签 `YYYY-MM`，Asia/Shanghai 月界）、`realized_profit_loss`（本月已实现盈亏）、`closed_count`（本月平仓笔数）、`triggered_count`（本月触发告警数）、`stop_adjustment_count` 与 `stop_lowered_count`（本月止损调整总次数与其中调低次数）、`largest_loss`（当前最大浮亏来源或 null）。既有响应字段 MUST 保持不变，空组合返回零值而非 null 聚合。

#### Scenario: 返回本月已实现盈亏与平仓笔数
- **WHEN** 用户请求 `GET /api/dashboard` 且本月存在已平仓持仓（成本、平仓价、数量可计算）
- **THEN** `month_summary.realized_profit_loss` 等于本月平仓 `(平仓价 − 买入价) × 数量` 之和，`closed_count` 等于本月平仓笔数

#### Scenario: 上月平仓不计入本月
- **WHEN** 存在上月平仓的持仓且本月无平仓
- **THEN** `month_summary.realized_profit_loss` 为 0 且 `closed_count` 为 0

#### Scenario: 返回本月触发与止损调整统计
- **WHEN** 本月存在触发告警与来源为 `update`/`rearm` 的止损调整记录
- **THEN** `triggered_count` 等于本月告警数，`stop_adjustment_count` 等于本月调整数，`stop_lowered_count` 只统计调整后止损价低于该持仓上一条历史记录的次数

#### Scenario: 返回最大浮亏来源
- **WHEN** 当前存在可估值的浮亏持仓
- **THEN** `largest_loss` 返回其中浮亏金额最大的名称、代码与负值浮亏额

#### Scenario: 无浮亏时最大亏损来源为空
- **WHEN** 所有可估值持仓均浮盈或无可估值持仓
- **THEN** `largest_loss` 为 null

#### Scenario: 空组合返回零值聚合
- **WHEN** 不存在任何持仓
- **THEN** `month_summary` 各计数为 0、`realized_profit_loss` 为 0、`largest_loss` 为 null，`month` 为当前 `YYYY-MM`

### Requirement: 展示本月账本卡片
前端仪表盘 SHALL 在行情可信摘要之后、待处置队列之前展示"本月账本"卡片：主导数字为本月已实现盈亏（按盈亏语义着色），副标题为平仓笔数；辅助行展示本月触发次数、止损调整次数（含调低次数）与当前浮亏参考（明确标注为当前快照）；`largest_loss` 非空时展示最大亏损来源；存在待处置项时提供"去处置"行动入口。卡片 MUST 与 `month_summary` 使用同一时区口径展示月份标签；`month_summary` 缺失或为空时 MUST 不渲染卡片；空组合显示零值。

#### Scenario: 展示本月已实现盈亏
- **WHEN** 用户打开仪表盘且响应包含 `month_summary`
- **THEN** 卡片主导数字显示本月已实现盈亏并按盈亏着色，副标题显示平仓笔数

#### Scenario: 展示触发与调整统计
- **WHEN** 本月存在触发或止损调整记录
- **THEN** 卡片辅助行显示本月触发次数与调整次数（含调低次数）

#### Scenario: 展示最大亏损来源
- **WHEN** `largest_loss` 非空
- **THEN** 卡片显示最大亏损来源的名称与浮亏金额

#### Scenario: 提供待处置行动入口
- **WHEN** 仪表盘存在待处置（已触发）持仓
- **THEN** 卡片提供"去处置"入口并导向告警或处置页面；无待处置时不显示入口

#### Scenario: 卡片数值与接口一致
- **WHEN** 用户刷新仪表盘
- **THEN** 卡片展示的本月已实现盈亏等数值与 `GET /api/dashboard` 的 `month_summary` 一致

#### Scenario: 空组合显示零值
- **WHEN** 不存在任何持仓
- **THEN** 卡片显示零值账本（本月已实现盈亏 0、计数 0），不显示虚假金额
