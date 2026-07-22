## ADDED Requirements

### Requirement: Retain history within configured bounds
系统 SHALL 按配置保留行情和诊断历史，以小批量删除过期普通点，并永久或按独立审计策略保留规则、触发和平仓关键事件。

#### Scenario: Retention cleanup runs
- **WHEN** 普通行情点超过保留期
- **THEN** 清理任务分批删除并避免长时间持有 SQLite 写锁

### Requirement: Downsample history on the server
历史 API SHALL 在服务端将普通序列下采样到最多 1000 点，同时保留所有关键事件标记。

#### Scenario: Large history query
- **WHEN** 查询窗口包含超过 1000 个普通点
- **THEN** 浏览器收到有界序列且触发、规则变更和平仓点仍完整
