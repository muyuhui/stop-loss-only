## ADDED Requirements

### Requirement: Record every monitoring cycle
系统 SHALL 持久化每次调度或手动监控周期的类型、状态、开始/结束时间、成功/跳过/失败数量、最近成功时间、覆盖率和稳定错误码，且不得保存价格、数量、成本或提供方原始响应。

#### Scenario: Mixed monitoring result
- **WHEN** 一个周期中部分标的成功且部分标的失败
- **THEN** 周期状态为 `partial`，分别记录计数和脱敏失败类别，并保留已提交成功结果

#### Scenario: Cycle is skipped
- **WHEN** 调度周期因互斥锁已被占用而跳过
- **THEN** 系统记录 `skipped` 周期和稳定原因，不启动第二次全市场下载

### Requirement: Expose actionable monitoring status
系统 SHALL 通过 `/api/monitoring/status` 返回调度器状态、下次运行、最近周期、最近成功、行情覆盖率和降级原因，并通过分页 `/api/monitoring/cycles` 提供稳定筛选的周期诊断。

#### Scenario: Monitoring is overdue
- **WHEN** 最近成功时间超过配置允许时长
- **THEN** 状态响应标记为过期并返回可操作的稳定原因码
