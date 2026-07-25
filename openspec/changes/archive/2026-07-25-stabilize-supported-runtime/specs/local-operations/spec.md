## MODIFIED Requirements

### Requirement: Migrate through explicit authority stages
系统 SHALL 在本稳定版本中只支持 `legacy` 与 `shadow-read` 运行阶段，且两者均以旧 `Holding` 模型作为唯一权威写源。系统 MUST 保留 shadow 重建与对账能力，但 MUST 拒绝进入 `new-authoritative`，直到后续 change 证明监控、历史、兼容 API、前端写入和恢复流程均使用新权威模型。

#### Scenario: 启用 shadow 诊断
- **WHEN** 用户从 `legacy` 启用 shadow read
- **THEN** 系统继续只向旧模型写入，并允许重建和对账新模型投影

#### Scenario: 尝试未支持的切换
- **WHEN** 用户在本稳定版本执行 cutover
- **THEN** 命令在备份、投影写入和权威状态修改前以非零状态退出，并返回稳定的 `cutover_not_supported` 原因

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

## REMOVED Requirements

### Requirement: Switch authority only at a controlled cutover
**Reason**: 以 Position 为权威的监控、历史、前端和兼容路径尚不完整，本版本无法安全支持切换。

**Migration**: 数据库保持在 `legacy` 或 `shadow-read`；未来 Position 切换 change 必须携带完整 E2E 与恢复证据后恢复该要求。

### Requirement: Preserve legacy API for one stable release
**Reason**: 在 Position 权威版本存在前，兼容窗口无法开始。

**Migration**: 在未来切换 change 启动兼容窗口前，继续把 legacy API 作为权威接口，而不是兼容投影。
