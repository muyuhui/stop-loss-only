# Monitoring Diagnostics

## Purpose

为本地单进程止损监控提供隐私安全的周期诊断、行情覆盖率、调度器健康和稳定降级原因，使用户能够判断当前行情是否足以支撑自动止损判断。

## Requirements

### Requirement: Record every monitoring cycle
系统 SHALL 持久化每次调度或手动监控周期的类型、状态、开始/结束时间、成功/跳过/失败数量、最近成功时间、覆盖率和稳定错误码，且不得保存价格、数量、成本或提供方原始响应。

#### Scenario: Mixed monitoring result
- **WHEN** 一个周期中部分标的成功且部分标的失败
- **THEN** 周期状态为 `partial`，分别记录计数和脱敏失败类别，并保留已提交成功结果

#### Scenario: Cycle is skipped
- **WHEN** 调度周期因互斥锁已被占用而跳过
- **THEN** 系统记录 `skipped` 周期和稳定原因，不启动第二次全市场下载

### Requirement: Expose actionable monitoring status
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

### Requirement: 明确零分母行情覆盖率
监控状态 SHALL 区分没有活动持仓的不可用覆盖率与存在活动持仓但没有任何覆盖的真实零覆盖率。`actionable_quote_coverage_pct`、`valuation_quote_coverage_pct` 及兼容别名 `quote_coverage_pct` MUST 保持一致的可用性语义。

#### Scenario: 没有活动持仓
- **WHEN** `holding` 和 `triggered` 状态的持仓总数为零
- **THEN** 可操作、估值及兼容覆盖率均返回 `null`，前端显示“暂无活动持仓”而不是 `100%`

#### Scenario: 活动持仓均未覆盖
- **WHEN** 存在一个或多个活动持仓且没有可操作行情或可估值行情
- **THEN** 对应覆盖率返回真实的 `0.0`，前端明确显示 `0%` 覆盖
