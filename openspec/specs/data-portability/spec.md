# data-portability Specification

## Purpose
TBD - created by archiving change extend-local-platform. Update Purpose after archive.
## Requirements
### Requirement: Preview CSV imports before mutation
系统 SHALL 对有大小、行数和编码限制的标准 CSV 进行零写入预览，返回短期本地令牌、规范化行和逐行稳定错误。

#### Scenario: Mixed valid and invalid rows
- **WHEN** 文件同时包含合法和非法行
- **THEN** 预览返回全部可展示结果且数据库不发生变化

### Requirement: Commit an approved import atomically
系统 SHALL 只提交未过期且内容未改变的预览令牌，并在单一事务中创建领域对象与导入事件。

#### Scenario: Preview token expires
- **WHEN** 用户提交过期令牌
- **THEN** 系统拒绝提交且不产生部分导入

### Requirement: Export stable and safe CSV
系统 SHALL 导出带 schema 版本和生成时间的稳定列，以不丢精度的文本表示 Decimal，并转义公式起始字符。

#### Scenario: Text begins with formula marker
- **WHEN** 名称以 `=`, `+`, `-` 或 `@` 开头
- **THEN** 导出值被安全转义且重新导入可恢复原文本

### Requirement: Create user-verifiable backups
设置界面 SHALL 只允许在受控备份目录创建带 checksum、schema 版本和 WAL 感知 manifest 的一致性备份；恢复 MUST 继续要求停服命令。

#### Scenario: Create backup from settings
- **WHEN** 用户确认创建备份
- **THEN** 系统返回备份文件名、校验状态和 schema 版本，不允许浏览器替换活动数据库

