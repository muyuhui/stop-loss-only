## MODIFIED Requirements

### Requirement: Create alert on stop-loss trigger
系统 SHALL 对每个持仓触发生命周期原子地创建至多一个告警，并保存持仓代码、名称、触发价、现价、行情时间、来源、未读状态和创建时间快照。

#### Scenario: 首次触发创建告警
- **WHEN** 新鲜有效行情首次使持仓从 `holding` 变为 `triggered`
- **THEN** 系统创建一个未读告警，并保存后续可独立解释该告警所需的持仓与行情快照

#### Scenario: 重复判断同一触发
- **WHEN** 调度器重试或并发刷新再次处理已触发持仓
- **THEN** 服务层和数据库幂等约束共同阻止重复告警

#### Scenario: 后续删除持仓
- **WHEN** 告警产生后源持仓被删除
- **THEN** 告警仍保留持仓名称、代码、价格和行情元数据

### Requirement: List alerts
系统 SHALL 按创建时间倒序返回分页告警列表，并使用告警自身快照，不依赖仍然存在的持仓记录。

#### Scenario: 查询全部告警
- **WHEN** 用户请求 `GET /api/alerts`
- **THEN** 系统按创建时间倒序返回告警快照及分页元数据

#### Scenario: 筛选未读告警
- **WHEN** 用户请求 `GET /api/alerts?unread=true`
- **THEN** 系统只返回未读状态为真的告警
