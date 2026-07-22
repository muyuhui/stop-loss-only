## ADDED Requirements

### Requirement: Track alert disposition separately from read state
告警 SHALL 分别记录阅读状态和风险处置状态，处置状态至少包含 `open`、`acknowledged`、`rearmed` 和 `closed`，并与对应仓位事件关联。

#### Scenario: Read without disposition
- **WHEN** 用户把一条开放告警标记已读
- **THEN** `read=true` 但 disposition 仍为 `open`

#### Scenario: Position is rearmed
- **WHEN** 用户从告警对应仓位完成重新布防
- **THEN** 告警 disposition 变为 `rearmed` 并关联新的规则事件

### Requirement: Show an actionable alert experience
前端 SHALL 支持阅读状态、处置状态、日期、标的和告警类型筛选，并提供进入仓位对应事件、确认风险、重新布防或记录平仓的明确入口。

#### Scenario: Filter unresolved alerts
- **WHEN** 用户选择“待处理”筛选
- **THEN** 页面只显示 disposition 为 `open` 的分页结果，并把筛选写入 URL query

#### Scenario: Mobile alert card
- **WHEN** 用户在 360px 到 767px 视口查看告警
- **THEN** 卡片完整显示标的、触发规则、行情状态、风险金额、时间和处置操作，不产生横向滚动

## MODIFIED Requirements

### Requirement: Create alert on stop-loss trigger
系统 SHALL 对每个仓位、规则和触发序列原子地创建至多一个告警，并保存标的、仓位、规则、止损价、现价、风险金额、行情状态、行情时间、来源、阅读状态、处置状态和创建时间快照。

#### Scenario: 首次触发创建告警
- **WHEN** 可行动行情首次使当前规则对应仓位从 `holding` 变为 `triggered`
- **THEN** 系统在同一事务创建未读且待处理的告警和触发事件，并保存可独立解释的完整快照

#### Scenario: 重复判断同一触发序列
- **WHEN** 调度器重试或并发刷新再次处理同一仓位和规则
- **THEN** 服务层条件更新和数据库幂等约束共同阻止重复事件与告警

#### Scenario: 后续删除或修改仓位
- **WHEN** 告警产生后源仓位被修改、重新布防或软删除
- **THEN** 告警仍使用自身保存的标的、规则、价格、风险和行情快照

### Requirement: List alerts
系统 SHALL 按处置优先级、创建时间和 ID 稳定返回分页告警列表，支持阅读状态、处置状态、日期、标的和类型白名单筛选，并使用告警自身快照。

#### Scenario: 查询默认告警列表
- **WHEN** 用户请求 `GET /api/alerts` 且不带筛选
- **THEN** 系统把待处理告警排在已处置告警之前，并在各组内按创建时间倒序返回分页元数据

#### Scenario: 筛选未读告警
- **WHEN** 用户请求 `GET /api/alerts?unread=true`
- **THEN** 系统只统计并返回未读告警

#### Scenario: 筛选待处理告警
- **WHEN** 用户请求 disposition 为 `open`
- **THEN** 系统只返回尚未确认、重新布防或关闭的告警

#### Scenario: 请求后续页
- **WHEN** 告警总数超过页面大小且用户请求下一页
- **THEN** items 返回对应稳定切片，前端提供可到达的分页操作
