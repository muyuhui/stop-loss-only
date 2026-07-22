## ADDED Requirements

### Requirement: Preview CSV imports before mutation
系统 SHALL 先解析并规范化 CSV，返回短期预览令牌、有效行和逐行错误，预览阶段不得写入正式持仓数据。

#### Scenario: Mixed valid and invalid rows
- **WHEN** CSV 同时包含有效行和无效价格、代码或日期
- **THEN** 预览返回每行状态和可理解错误，数据库保持不变

#### Scenario: Oversized import
- **WHEN** 文件大小或行数超过配置限制
- **THEN** 系统拒绝解析并返回稳定错误码

### Requirement: Commit an approved import atomically
系统 SHALL 只接受未过期且内容未变化的预览令牌，并按用户选择以全有或全无方式提交有效数据。

#### Scenario: Commit valid preview
- **WHEN** 用户确认一个全部有效且未过期的预览
- **THEN** 系统事务性创建对应标的、仓位、批次、规则和导入事件

#### Scenario: Preview token expires
- **WHEN** 用户提交已过期预览令牌
- **THEN** 系统返回冲突错误且不创建任何业务记录

### Requirement: Export stable and safe CSV
系统 SHALL 使用带 schema 版本、生成时间和明确列名的 UTF-8 CSV 导出仓位、批次和关闭数据，十进制值不得丢失精度，潜在公式内容必须安全转义。

#### Scenario: Export portfolio data
- **WHEN** 用户请求导出全部仓位
- **THEN** 文件包含活动和关闭仓位、批次、规则及收益字段，并能被项目导入器重新解析

#### Scenario: Text begins with formula marker
- **WHEN** 名称或备注以 `=`, `+`, `-` 或 `@` 开头
- **THEN** 导出器转义该值以防止电子表格执行公式

### Requirement: Create user-verifiable backups
系统 SHALL 允许用户在受控目录创建一致性数据库快照和 checksum manifest，并在 UI 中展示文件位置、schema 版本和校验结果。

#### Scenario: Create backup from settings
- **WHEN** 用户确认创建备份
- **THEN** 系统生成不覆盖既有文件的新快照和 manifest，并通过完整性检查
