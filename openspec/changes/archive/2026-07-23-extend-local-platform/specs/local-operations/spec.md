## ADDED Requirements

### Requirement: Validate WAL-aware backup and restore
备份 SHALL 使用 SQLite 一致性快照并记录 checksum、schema 版本和完整性信息；恢复 MUST 在替换前验证 manifest、支持的 schema、目标路径和数据库完整性，并创建当前数据库恢复点。

#### Scenario: Restored database fails readiness
- **WHEN** 替换后的数据库未通过 readiness
- **THEN** 系统自动还原替换前恢复点并返回非零结果

### Requirement: Export privacy-aware diagnostics
系统 SHALL 在导出诊断包前展示包含内容，默认排除数据库、密钥、价格、数量、成本和原始提供方响应，并允许用户进一步排除类别。

#### Scenario: Create default diagnostic package
- **WHEN** 用户按默认选项导出诊断
- **THEN** 包中只含脱敏配置、版本、周期摘要和稳定错误码

### Requirement: Report and maintain bounded storage
系统 SHALL 提供数据库大小、历史保留和分批清理状态，并在 WAL、busy timeout 和外键设置下验证备份与维护任务。

#### Scenario: Cleanup encounters busy database
- **WHEN** 清理批次超过 busy timeout
- **THEN** 任务安全停止并保留下次可恢复进度，不阻塞监控主流程
