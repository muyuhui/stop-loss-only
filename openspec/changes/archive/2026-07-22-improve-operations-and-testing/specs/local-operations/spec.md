## ADDED Requirements

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
