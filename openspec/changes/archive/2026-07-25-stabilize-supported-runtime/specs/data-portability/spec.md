## ADDED Requirements

### Requirement: 可移植格式无法表示权威事实时默认拒绝
本稳定版本 SHALL 不显示 CSV 导入导出控件，并 SHALL 拒绝对应公共 HTTP 操作，直到 CSV 能无损表示当前权威模型且导入记录会立即进入受支持列表与监控。数据库备份与停服恢复继续作为受支持的数据可恢复路径。

#### Scenario: 直接请求 CSV 导入
- **WHEN** 客户端绕过前端直接请求 CSV 预览或提交
- **THEN** 系统返回稳定的 `feature_not_supported`，且 Holding、Position 和导入审计表均不发生变化

#### Scenario: 用户需要可携带恢复产物
- **WHEN** 用户在稳定版本创建数据恢复点
- **THEN** 系统提供经过校验的 SQLite 备份和 manifest，而不声称 CSV 可完整恢复当前数据

## REMOVED Requirements

### Requirement: Preview CSV imports before mutation
**Reason**: 当前预览最终只提交 Position 记录，而稳定权威模型是 Holding。

**Migration**: 停用接口和 UI，直到未来可移植性 change 面向当前权威模型并具备完整逐行测试。

### Requirement: Commit an approved import atomically
**Reason**: 当前成功提交会创建受支持持仓 UI 和监控引擎均不可见的记录。

**Migration**: 使用经过验证的数据库备份恢复；只有导入记录与权威模型一致可见并通过监控验收测试后才重新启用。

### Requirement: Export stable and safe CSV
**Reason**: 当前导出遗漏 legacy 持仓，且无法无损表示多批次 Position 核算。

**Migration**: 保持导出停用，直到重新设计 schema 并针对当前权威模型完成往返验证。
