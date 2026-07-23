## ADDED Requirements

### Requirement: Migrate through explicit authority stages
系统 SHALL 使用有序 migration 将数据库依次置于 `legacy`、`shadow-read` 和 `new-authoritative` 阶段，并在每个阶段记录唯一事实来源；MUST NOT 同时把新旧模型声明为权威写源。

#### Scenario: Shadow comparison succeeds
- **WHEN** 旧模型写入后的新模型投影与数量、成本、状态、止损价、告警和汇总全部一致
- **THEN** 系统记录成功对账，但在受控切换前仍由旧模型响应

#### Scenario: Shadow comparison fails
- **WHEN** 任一关键对账项不一致
- **THEN** 系统阻止进入 `new-authoritative` 并暴露不含敏感值的 readiness 原因

#### Scenario: Post-commit projection is interrupted
- **WHEN** 旧模型事务已经提交但进程在 shadow 投影完成前退出
- **THEN** 旧模型继续作为唯一权威事实，shadow 被视为 dirty，幂等全量重建与对账成功前不得切换权威模式

### Requirement: Switch authority only at a controlled cutover
系统 SHALL 在停止调度和业务写入、创建校验备份、完成最终投影与对账后原子切换到新模型权威模式；切换后的回滚 MUST 使用经验证的反向迁移或备份恢复。

#### Scenario: Cutover validation fails
- **WHEN** 最终对账、备份或 readiness 任一步失败
- **THEN** 系统保持旧模型权威且不得开放新模型专属写操作

### Requirement: Preserve legacy API for one stable release
系统 SHALL 在新版 positions API 正式发布后的一个稳定版本内，将新模型映射为旧 holdings 和 dashboard DTO；移除旧接口必须由独立 change 执行。

#### Scenario: Legacy route after cutover
- **WHEN** 客户端在兼容期调用旧持仓路由
- **THEN** 响应由新权威模型映射并满足已固化契约
