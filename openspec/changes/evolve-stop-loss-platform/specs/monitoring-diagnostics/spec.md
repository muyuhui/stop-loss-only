## ADDED Requirements

### Requirement: Record every monitoring cycle
系统 SHALL 为每次调度或手动监控创建持久化周期记录，包含周期类型、市场状态、开始/结束时间、请求/成功/失败/过期/触发数量、结果状态和稳定错误码，且不得记录敏感价格或数量。

#### Scenario: Successful scheduled cycle
- **WHEN** 调度器在交易时段完成一次全部成功的行情周期
- **THEN** 系统保存状态为 `ok` 的周期及准确聚合数量

#### Scenario: Cycle has mixed quote results
- **WHEN** 同一周期部分标的成功、部分失败或过期
- **THEN** 系统保存状态为 `partial` 的周期并分别统计各类结果

#### Scenario: Scheduled cycle is skipped
- **WHEN** 调度任务在非交易时段运行
- **THEN** 系统保存状态为 `skipped` 的周期、跳过原因和市场状态，且不调用行情提供方

### Requirement: Expose actionable monitoring status
系统 SHALL 提供轻量监控状态接口，返回调度器运行状态、下次运行时间、最近周期、最近成功时间、行情覆盖率、降级状态和可公开的提供方健康摘要。

#### Scenario: Monitoring is healthy
- **WHEN** 调度器运行且最近周期成功并在预期间隔内
- **THEN** 接口返回 `healthy`、最近成功时间和完整行情覆盖率

#### Scenario: Monitoring data is overdue
- **WHEN** 最近成功周期早于配置间隔的两倍
- **THEN** 接口返回 `degraded` 和稳定原因 `monitoring_overdue`

#### Scenario: Scheduler is disabled
- **WHEN** 开发模式显式关闭调度器
- **THEN** 接口返回 `disabled` 而不是错误地声称监控异常

### Requirement: Retain bounded provider diagnostics
系统 SHALL 记录提供方调用的结果、耗时、错误类别和熔断状态，并按保留策略清理，不得保存完整外部响应或持仓敏感字段。

#### Scenario: Provider times out
- **WHEN** 行情提供方超过配置总超时
- **THEN** 本轮标记 `provider_timeout`，诊断记录包含耗时和提供方名称但不包含原始响应

#### Scenario: Diagnostics exceed retention
- **WHEN** 诊断记录早于配置保留时间
- **THEN** 后台清理任务分批删除旧记录且不阻塞新的监控周期
