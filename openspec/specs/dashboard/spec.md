# Dashboard

## Purpose

Provide a portfolio overview dashboard with summary metrics, holdings status, and alert information.
## Requirements
### Requirement: Portfolio summary
系统 SHALL 将 `holding`、`triggered` 的当前敞口和未实现收益，与 `closed` 的毛已实现收益分开计算，并返回各生命周期数量。

#### Scenario: 同时存在活动和已关闭持仓
- **WHEN** 组合中包含当前持仓和已关闭持仓
- **THEN** 系统分别计算活动成本、活动市值、未实现收益、毛已实现收益及状态数量

#### Scenario: 没有持仓
- **WHEN** 组合为空
- **THEN** 所有金额和状态数量均为零

### Requirement: Holdings overview list
系统 SHALL 从 legacy `Holding` 权威模型列出 `holding` 和 `triggered` 记录，并返回与稳定持仓 API 一致的标识、价格、行情元数据、止损字段、状态、收益率和止损距离。每个详情入口 MUST 指向已注册的 `/holdings/:id` 页面。

#### Scenario: 查看风险持仓
- **WHEN** 仪表盘显示一个活动或已触发持仓
- **THEN** 用户可以从桌面表格或移动卡片进入对应的稳定持仓详情

### Requirement: Today's alert summary
系统 SHALL 按 Asia/Shanghai 自然日边界返回今日告警数和最新告警快照。

#### Scenario: 今日存在告警
- **WHEN** 当前上海自然日内创建过告警
- **THEN** 仪表盘返回告警数量和最新一条快照

#### Scenario: 今日没有告警
- **WHEN** 当前上海自然日内没有告警
- **THEN** 今日告警数为零，最新告警为 null

### Requirement: Frontend dashboard layout
前端 SHALL 以风险优先的层级展示仪表盘：首先呈现监控可信度、组合风险和待处理告警，其次呈现有覆盖语义的盈亏、市值与成本摘要，最后呈现按已知止损距离排序的活动持仓和紧凑的今日告警摘要。可选区域 SHALL 仅在对应运行时能力可用时出现，布局 SHALL 根据视口宽度重排而不产生页面级横向滚动。

#### Scenario: 桌面端加载成功
- **WHEN** 用户在至少 1024px 宽的视口打开仪表盘且请求成功
- **THEN** 页面先显示可信度和风险摘要，再显示资产指标、持仓概览和今日告警，并直接展示需要处理的告警数量

#### Scenario: 手机端加载成功
- **WHEN** 用户在 360px 到 767px 宽的视口打开仪表盘且请求成功
- **THEN** 摘要以不超过两列的结构排列，持仓使用适合窄屏的完整摘要卡片，页面不出现横向滚动

#### Scenario: 存在临近止损持仓
- **WHEN** 多个活动持仓具有不同的已知止损距离
- **THEN** 持仓概览按止损距离从近到远排列，并使临近或已触发项具有明确的非颜色风险提示

#### Scenario: 所有活动持仓风险未知
- **WHEN** 存在活动持仓但其止损距离全部不可用，且没有已触发持仓或未读告警
- **THEN** 组合风险摘要显示“风险状态待定”而不是“风险平稳”，未知持仓排在所有已知距离之后

#### Scenario: 今日没有告警
- **WHEN** 今日告警数为零且最新告警为 null
- **THEN** 页面使用紧凑状态提示表达暂无告警，不保留大面积空白告警面板

#### Scenario: 风险预算能力不可用
- **WHEN** 运行时能力将 `risk_budget_reads` 标记为不可用
- **THEN** 仪表盘不请求风险预算 API，也不渲染风险预算卡片或未启用说明，风险与持仓主流程直接占据该空间

### Requirement: Real-time frontend refresh
前端 SHALL 使用生效的运行时轮询间隔刷新仪表盘，并保证最多只有一个仪表盘计时器。

#### Scenario: 自动刷新
- **WHEN** 仪表盘已挂载且配置间隔到期
- **THEN** 数据自动刷新，无需重载页面

#### Scenario: 间隔动态变化
- **WHEN** 仪表盘挂载期间轮询设置发生变化
- **THEN** 清除旧计时器并按新间隔只启动一个计时器

#### Scenario: 离开仪表盘
- **WHEN** 用户导航离开仪表盘
- **THEN** 清除活动计时器

### Requirement: 仪表盘刷新可感知
前端 SHALL 在仪表盘展示最后成功更新时间，并区分首次加载、后台刷新、刷新失败和数据可能过期状态。

#### Scenario: 后台轮询成功
- **WHEN** 仪表盘已有数据且下一次轮询成功
- **THEN** 页面平稳更新内容和最后更新时间，不清空持仓或闪回初始零值

#### Scenario: 后台轮询失败
- **WHEN** 仪表盘已有数据且下一次轮询失败
- **THEN** 页面保留现有数据并提供轻量失败提示和手动重试入口

### Requirement: Return Decimal-safe portfolio accounting summaries
仪表盘 API SHALL 只从当前受支持的 legacy `Holding` 权威模型计算开放成本、可估值市值、未实现盈亏、已实现盈亏、生命周期数量和行情覆盖信息，并 MUST NOT 将 shadow `Position` 数据混入同一响应。财务中间计算 SHALL 使用 Decimal，响应保持冻结的仪表盘契约。

#### Scenario: 存在 shadow 投影
- **WHEN** 数据库同时包含 legacy holdings 和对应 shadow positions
- **THEN** 仪表盘只计算一次 legacy 权威事实且结果不因 shadow 重建而变化

#### Scenario: 持仓没有可用行情
- **WHEN** 活动持仓尚无可估值行情
- **THEN** 仪表盘排除该实时估值、保留成本事实并明确降低覆盖率

### Requirement: Present monitoring trust before portfolio totals
仪表盘 SHALL 在首屏持续显示市场/调度状态、最近成功时间、可行动行情覆盖率、失败数量和诊断入口，并将待处理风险置于普通资产汇总之前。

#### Scenario: Monitoring is degraded without trigger
- **WHEN** 最新监控周期降级但没有仓位触发
- **THEN** 页面明确显示监控降级，且不得用“安全”视觉掩盖数据不可信

#### Scenario: Background refresh fails
- **WHEN** 后台刷新失败但存在上次成功数据
- **THEN** 页面保留上次数据、显示年龄和错误状态，不清空仪表盘

### Requirement: Use a responsive risk-first dashboard layout
仪表盘 SHALL 在桌面展示高密度风险表，在移动端展示紧凑行动摘要，并避免固定导航遮挡、横向滚动和关键状态截断。

#### Scenario: Mobile dashboard
- **WHEN** 视口为 390x844
- **THEN** 风险行动、行情可信度和关键指标无需横向滚动即可访问

