## ADDED Requirements

### Requirement: 明确零分母行情覆盖率
监控状态 SHALL 区分没有活动持仓的不可用覆盖率与存在活动持仓但没有任何覆盖的真实零覆盖率。`actionable_quote_coverage_pct`、`valuation_quote_coverage_pct` 及兼容别名 `quote_coverage_pct` MUST 保持一致的可用性语义。

#### Scenario: 没有活动持仓
- **WHEN** `holding` 和 `triggered` 状态的持仓总数为零
- **THEN** 可操作、估值及兼容覆盖率均返回 `null`，前端显示“暂无活动持仓”而不是 `100%`

#### Scenario: 活动持仓均未覆盖
- **WHEN** 存在一个或多个活动持仓且没有可操作行情或可估值行情
- **THEN** 对应覆盖率返回真实的 `0.0`，前端明确显示 `0%` 覆盖
