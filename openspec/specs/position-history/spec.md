# position-history Specification

## Purpose
TBD - created by archiving change introduce-position-domain. Update Purpose after archive.
## Requirements
### Requirement: Preserve immutable position events
系统 SHALL 为仓位开启、加仓、规则启用、触发、风险确认、重新布防、部分平仓、关闭和元数据修改创建带 schema 版本的不可变事件。

#### Scenario: Position is rearmed
- **WHEN** 用户以新规则和原因重新布防
- **THEN** 系统保留旧触发与告警，并追加风险覆盖和规则启用事件

#### Scenario: Business record is soft deleted
- **WHEN** 用户删除允许删除的业务对象
- **THEN** 相关审计事件和告警快照仍可查询

### Requirement: Query bounded history
系统 SHALL 提供分页事件时间线和有界行情/止损线序列，返回最多 1000 个图表点并保留触发、规则变更和平仓关键点。

#### Scenario: Query a one-year history
- **WHEN** 原始点超过返回上限
- **THEN** 服务端下采样普通点并保留全部关键事件点

### Requirement: Retain history within configured bounds
系统 SHALL 按配置保留行情和诊断历史，以小批量删除过期普通点，并永久或按独立审计策略保留规则、触发和平仓关键事件。

#### Scenario: Retention cleanup runs
- **WHEN** 普通行情点超过保留期
- **THEN** 清理任务分批删除并避免长时间持有 SQLite 写锁

