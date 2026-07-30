## MODIFIED Requirements

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
