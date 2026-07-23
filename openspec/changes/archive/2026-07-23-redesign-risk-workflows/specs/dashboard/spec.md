## ADDED Requirements

### Requirement: Present monitoring trust before portfolio totals
仪表盘 SHALL 在首屏持续显示市场/调度状态、最近成功时间、可行动行情覆盖率、失败数量和诊断入口，并将待处理风险置于普通资产汇总之前。

#### Scenario: Monitoring is degraded without trigger
- **WHEN** 最新监控周期降级但没有仓位触发
- **THEN** 页面明确显示监控降级，且不得用“安全”视觉掩盖数据不可信

#### Scenario: Background refresh fails
- **WHEN** 后台刷新失败但存在上次成功数据
- **THEN** 页面保留上次数据、显示年龄和错误状态，不清空仪表盘

### Requirement: Use a responsive risk-first dashboard layout
仪表盘 SHALL 在桌面展示高密度风险表，在移动端展示紧凑行动摘要，并避免固定导航遮挡、横向滚动和关键状态截断。

#### Scenario: Mobile dashboard
- **WHEN** 视口为 390x844
- **THEN** 风险行动、行情可信度和关键指标无需横向滚动即可访问
