# Local Operations

## Purpose

为本地单用户部署提供安全、可观测且可恢复的完整运维约束，统一数据库迁移与备份恢复、进程启动和停止、调度器所有权以及健康诊断行为，避免启动脚本误杀无关进程、schema 漂移或故障信息泄露持仓数据。
## Requirements
### Requirement: 显式数据库迁移
系统 SHALL 记录数据库 schema revision，并通过版本化、可回滚迁移更新 schema，不得在模块导入时创建或修改正式数据表。

#### Scenario: 数据库版本符合预期
- **WHEN** 后端执行 readiness 检查
- **THEN** schema 兼容检查成功，且检查过程不修改数据库结构

#### Scenario: 存在待执行或未知 revision
- **WHEN** 启动时发现 schema 不兼容
- **THEN** readiness 失败并给出可执行的迁移提示，监控任务不得启动

#### Scenario: 验证迁移降级
- **WHEN** revision 声明支持 downgrade
- **THEN** 自动化测试可以在代表性数据库上升级和降级，且不丢失无关记录

### Requirement: 可验证的备份与恢复
系统 SHALL 使用一致性 SQLite 快照、checksum manifest、schema revision 和完整性校验提供显式备份恢复命令，并保证替换过程可恢复。

#### Scenario: 创建备份
- **WHEN** 用户对有效数据库执行备份命令
- **THEN** 系统创建新的时间戳快照与 manifest，并通过 checksum 和 SQLite 完整性校验

#### Scenario: 恢复有效备份
- **WHEN** 服务已停止且用户恢复兼容的有效快照
- **THEN** 替换数据库在启用前通过完整性和 schema 校验

#### Scenario: 恢复校验失败
- **WHEN** checksum、完整性或 schema 兼容校验失败
- **THEN** 恢复中止，现有活动数据库不被替换

### Requirement: 安全的本地进程生命周期
正常启动 SHALL 默认把服务绑定到 loopback、后端不启用 reload、只验证而不安装依赖，并且不得终止无关端口占用者。停止命令 SHALL 只处理经验证属于本项目的记录进程。启动前 MUST 验证后端导入和前端已安装依赖与 lockfile 完整一致，而不是只检查依赖目录存在。

#### Scenario: 端口可用且依赖完整
- **WHEN** 配置、后端导入、前端依赖图有效且端口空闲
- **THEN** 一个后端和一个前端进程在 loopback 启动，并报告 readiness

#### Scenario: 前端依赖目录不完整
- **WHEN** `node_modules` 存在但 lockfile 声明的任一直接依赖缺失
- **THEN** 启动在创建服务进程前失败并显示明确 setup 命令

#### Scenario: 端口被其他进程占用
- **WHEN** 启动发现无关监听进程
- **THEN** 启动失败并报告端口和所有者，不终止该进程

#### Scenario: PID 已被复用
- **WHEN** 停止命令发现记录 PID 已不属于当前工作区命令
- **THEN** 保留该进程、不删除无关数据，并报告不匹配

### Requirement: 单一调度器所有者
受支持的正常部署 SHALL 只运行一个调度器所有者，在启动前恢复持久化间隔，并随应用 lifespan 优雅关闭。

#### Scenario: 正常启动后端
- **WHEN** 一个受支持的后端进程就绪
- **THEN** 恰好启动一个调度器，并使用生效的持久化间隔

#### Scenario: 使用开发热重载
- **WHEN** 开发命令使用 reload 且未显式开启调度器
- **THEN** 行情监控保持关闭，控制台明确提示

#### Scenario: 后端关闭
- **WHEN** 后端收到正常终止信号
- **THEN** 调度器停止接受新周期，活动周期按策略完成或超时，数据库资源关闭

### Requirement: 运维诊断
系统 SHALL 输出隐私友好的结构化日志，并提供互相独立的 liveness 和 readiness；readiness 不依赖外部行情源可用性。

#### Scenario: 请求或监控周期结束
- **WHEN** API 请求或监控周期完成
- **THEN** 日志包含关联标识、组件、结果、耗时和聚合计数，不包含持仓价格、数量或完整响应体

#### Scenario: 进程存活但 schema 不兼容
- **WHEN** 在该状态查询健康接口
- **THEN** liveness 成功，readiness 以非敏感原因失败

#### Scenario: 外部行情源不可用
- **WHEN** 本地依赖健康但行情源无法访问
- **THEN** readiness 仍由本地服务状态决定，行情失败通过监控诊断报告

### Requirement: Migrate through explicit authority stages
系统 SHALL 在本稳定版本中只支持 `legacy` 与 `shadow-read` 运行阶段，且两者均以旧 `Holding` 模型作为唯一权威写源。系统 MUST 保留 shadow 重建与对账能力，但 MUST 拒绝进入 `new-authoritative`，直到后续 change 证明监控、历史、兼容 API、前端写入和恢复流程均使用新权威模型。

#### Scenario: 启用 shadow 诊断
- **WHEN** 用户从 `legacy` 启用 shadow read
- **THEN** 系统继续只向旧模型写入，并允许重建和对账新模型投影

#### Scenario: 尝试未支持的切换
- **WHEN** 用户在本稳定版本执行 cutover
- **THEN** 命令在备份、投影写入和权威状态修改前以非零状态退出，并返回稳定的 `cutover_not_supported` 原因

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

### Requirement: 删除恢复工作副本
恢复流程 SHALL 使用目标目录内的工作副本完成完整性校验与替换，并在成功和失败后删除该工作副本；同时 MUST 按照既有回滚契约保护活动数据库和已记录的恢复点。

#### Scenario: 恢复成功
- **WHEN** 兼容备份通过校验和、数据库结构和 SQLite 完整性检查，并替换活动数据库
- **THEN** 活动数据库包含恢复后的快照，恢复前的恢复点仍然可用，且不遗留恢复工作副本

#### Scenario: 替换前恢复失败
- **WHEN** 备份或工作副本在替换活动数据库之前校验失败
- **THEN** 活动数据库保持不变，所有恢复工作副本均被删除

#### Scenario: 替换开始后恢复失败
- **WHEN** 替换或复制后校验发生错误
- **THEN** 系统从恢复点复制回活动路径，操作以非零状态失败，并删除工作副本

#### Scenario: 工作副本清理失败
- **WHEN** 运行时无法删除恢复工作副本
- **THEN** 命令返回稳定的清理失败，且不删除活动数据库或恢复点，也不暴露财务数据内容

