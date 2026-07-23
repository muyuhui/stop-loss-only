## ADDED Requirements

### Requirement: Retain history within configured bounds
系统 SHALL 按配置保留行情和诊断历史，以小批量删除过期普通点，并永久或按独立审计策略保留规则、触发和平仓关键事件。

#### Scenario: Retention cleanup runs
- **WHEN** 普通行情点超过保留期
- **THEN** 清理任务分批删除并避免长时间持有 SQLite 写锁
