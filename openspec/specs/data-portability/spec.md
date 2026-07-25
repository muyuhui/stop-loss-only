# data-portability Specification

## Purpose
定义稳定版本的数据携带与恢复边界；当前只支持可校验的 SQLite 备份恢复，并在 CSV 无法无损表示权威事实时默认拒绝导入导出。
## Requirements
### Requirement: 可移植格式无法表示权威事实时默认拒绝
本稳定版本 SHALL 不显示 CSV 导入导出控件，并 SHALL 拒绝对应公共 HTTP 操作，直到 CSV 能无损表示当前权威模型且导入记录会立即进入受支持列表与监控。数据库备份与停服恢复继续作为受支持的数据可恢复路径。

#### Scenario: 直接请求 CSV 导入
- **WHEN** 客户端绕过前端直接请求 CSV 预览或提交
- **THEN** 系统返回稳定的 `feature_not_supported`，且 Holding、Position 和导入审计表均不发生变化

#### Scenario: 用户需要可携带恢复产物
- **WHEN** 用户在稳定版本创建数据恢复点
- **THEN** 系统提供经过校验的 SQLite 备份和 manifest，而不声称 CSV 可完整恢复当前数据

### Requirement: Create user-verifiable backups
设置界面 SHALL 只允许在受控备份目录创建带 checksum、schema 版本和 WAL 感知 manifest 的一致性备份；恢复 MUST 继续要求停服命令。

#### Scenario: Create backup from settings
- **WHEN** 用户确认创建备份
- **THEN** 系统返回备份文件名、校验状态和 schema 版本，不允许浏览器替换活动数据库

