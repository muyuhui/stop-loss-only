# Runtime Capabilities

## Purpose

定义稳定且不包含敏感信息的运行时能力契约，使后端就绪检查、路由守卫和前端功能开关共享同一套权威阶段策略。

## Requirements

### Requirement: 暴露实际运行时能力
系统 SHALL 提供 `GET /api/runtime/capabilities` 这一不包含敏感信息的只读契约。响应包含当前权威阶段、该阶段是否受稳定运行时支持，以及旧持仓写入、风险预算读取、只读风险试算、受风险约束的仓位创建、Position 生命周期写入、CSV 数据迁移和 Webhook 投递等明确的布尔能力。风险试算能力 MUST 与任何业务写入能力分别声明。

#### Scenario: 旧版权威阶段
- **WHEN** 当前权威阶段为 `legacy`
- **THEN** 响应将稳定运行时、旧持仓写入、风险预算读取和只读风险试算标记为可用，并将受风险约束的 Position 创建及所有 Position 生命周期写入标记为不可用

#### Scenario: 影子读取阶段
- **WHEN** 当前权威阶段为 `shadow-read`
- **THEN** 响应继续支持旧持仓写入和只读风险试算，声明影子诊断可用，且不声明任何 Position 写入能力

#### Scenario: 不受支持的新权威数据库
- **WHEN** 当前权威阶段为 `new-authoritative`
- **THEN** 响应将该阶段标记为不受稳定运行时支持，仅描述隔离 API 已实现的风险读取、试算及受风险约束创建能力，并且 MUST NOT 将未完成的 Position 生命周期写入声明为可用

#### Scenario: 只读试算不暗示写入能力
- **WHEN** `risk_plan_previews=true` 且 `risk_covered_position_creation=false`
- **THEN** 前端允许进入新仓和加仓试算，但不展示或调用 Position 创建、批次写入或 Holding 修改操作

### Requirement: 从唯一服务端策略生成能力
就绪检查、路由和运行时能力响应 SHALL 从同一套服务端策略获取权威阶段支持与功能可用性，不得在多个模块中重复维护阶段规则。

#### Scenario: 能力策略发生变化
- **WHEN** 后续变更为某个权威阶段启用一项能力
- **THEN** 就绪检查、直接 API 守卫和能力响应使用相同的策略结果

### Requirement: 保证能力发现安全且稳定
能力发现 SHALL 不执行任何业务写入，不暴露数据库路径、密钥、持仓价值、行情源载荷或进程标识，并为前端功能开关提供稳定字段名。

#### Scenario: 本地匿名读取能力
- **WHEN** 前端在应用启动时请求运行时能力
- **THEN** 响应仅包含权威阶段和功能支持元数据，且不修改任何数据库记录

### Requirement: 独立声明 AI 持仓复盘能力
运行时能力契约 SHALL 增加稳定布尔字段 `ai_holding_reviews`，其值只表示当前权威阶段和稳定运行面是否实现该能力，不包含 DeepSeek Key 是否已配置、Provider 错误、持仓事实或其他敏感信息。AI 路由守卫和前端入口 MUST 使用同一服务端能力策略。

#### Scenario: legacy 稳定运行面
- **WHEN** 当前权威阶段为受支持的 `legacy`
- **THEN** 能力响应声明 `ai_holding_reviews=true`，前端可以展示复盘入口或配置引导

#### Scenario: shadow-read 稳定运行面
- **WHEN** 当前权威阶段为受支持的 `shadow-read`
- **THEN** 能力响应继续声明 `ai_holding_reviews=true`，复盘只读取 legacy Holding 权威事实

#### Scenario: 不受支持的新权威运行面
- **WHEN** 当前权威阶段为 `new-authoritative`
- **THEN** 能力响应声明 `ai_holding_reviews=false`，前端隐藏复盘命令且直接 API 请求稳定拒绝

#### Scenario: 能力可用但 Key 未配置
- **WHEN** `ai_holding_reviews=true` 但本机没有 DeepSeek Key
- **THEN** 能力响应仍保持结构性能力为 true，设置响应单独报告未配置，持仓详情入口引导用户配置而不泄露任何密钥状态到公开能力元数据之外
