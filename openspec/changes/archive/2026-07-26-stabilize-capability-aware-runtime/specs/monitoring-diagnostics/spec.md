## MODIFIED Requirements

### Requirement: 暴露可操作的监控状态
系统 SHALL 通过 `/api/monitoring/status` 返回调度器状态、下次运行时间、最近周期、最近成功行情周期、交易日历感知的新鲜度、可操作行情覆盖率、估值行情覆盖率和稳定的降级原因，并通过 `/api/monitoring/cycles` 提供稳定的筛选分页。现有 `quote_coverage_pct` 和 `overdue` 字段 SHALL 分别保持为可操作覆盖率和真实监控过期状态的兼容别名。

#### Scenario: 应开市期间监控过期
- **WHEN** 当前应当出现可操作行情周期，但距最近成功行情时间已超过配置容限
- **THEN** 状态返回过期的新鲜度，将 `overdue` 设为 `true`，并返回稳定的可操作原因代码

#### Scenario: 权威交易日历表明休市
- **WHEN** 最近一次计划周期根据权威交易日历以 `market_closed` 跳过，且当前不应出现可操作行情周期
- **THEN** 状态返回休市新鲜度，将 `overdue` 设为 `false`，保留最近成功行情时间，且不把该跳过周期呈现为运维故障

#### Scenario: 收盘价只支持估值
- **WHEN** 活跃持仓拥有保留的收盘价或其他不可操作价格
- **THEN** 估值覆盖率包含这些持仓，可操作覆盖率不包含这些持仓

#### Scenario: 无法确定覆盖率
- **WHEN** 后端无法确定覆盖率分母或可信的分子
- **THEN** 对应覆盖率字段返回不可用，且 MUST NOT 表示为零
