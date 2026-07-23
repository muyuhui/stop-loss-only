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
正常启动 SHALL 默认把服务绑定到 loopback、后端不启用 reload、只验证而不安装依赖，并且不得终止无关端口占用者。停止命令 SHALL 只处理经验证属于本项目的记录进程。

#### Scenario: 端口可用
- **WHEN** 配置和依赖有效且端口空闲
- **THEN** 一个后端和一个前端进程在 loopback 启动，并报告 readiness

#### Scenario: 端口被其他进程占用
- **WHEN** 启动发现无关监听进程
- **THEN** 启动失败并报告端口和所有者，不终止该进程

#### Scenario: PID 已被复用
- **WHEN** 停止命令发现记录 PID 已不属于当前工作区命令
- **THEN** 保留该进程、不删除无关数据，并报告不匹配

#### Scenario: 缺少依赖
- **WHEN** 正常启动发现运行依赖缺失
- **THEN** 退出并显示明确 setup 命令，不自动安装软件包

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

