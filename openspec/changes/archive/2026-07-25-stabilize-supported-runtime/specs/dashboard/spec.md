## MODIFIED Requirements

### Requirement: Return Decimal-safe portfolio accounting summaries
仪表盘 API SHALL 只从当前受支持的 legacy `Holding` 权威模型计算开放成本、可估值市值、未实现盈亏、已实现盈亏、生命周期数量和行情覆盖信息，并 MUST NOT 将 shadow `Position` 数据混入同一响应。财务中间计算 SHALL 使用 Decimal，响应保持冻结的仪表盘契约。

#### Scenario: 存在 shadow 投影
- **WHEN** 数据库同时包含 legacy holdings 和对应 shadow positions
- **THEN** 仪表盘只计算一次 legacy 权威事实且结果不因 shadow 重建而变化

#### Scenario: 持仓没有可用行情
- **WHEN** 活动持仓尚无可估值行情
- **THEN** 仪表盘排除该实时估值、保留成本事实并明确降低覆盖率

### Requirement: Holdings overview list
系统 SHALL 从 legacy `Holding` 权威模型列出 `holding` 和 `triggered` 记录，并返回与稳定持仓 API 一致的标识、价格、行情元数据、止损字段、状态、收益率和止损距离。每个详情入口 MUST 指向已注册的 `/holdings/:id` 页面。

#### Scenario: 查看风险持仓
- **WHEN** 仪表盘显示一个活动或已触发持仓
- **THEN** 用户可以从桌面表格或移动卡片进入对应的稳定持仓详情
