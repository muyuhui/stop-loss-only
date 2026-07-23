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
系统 SHALL 在仪表盘中列出 `holding` 和 `triggered`，并返回与持仓 API 一致的标识、价格、行情元数据、止损字段、状态、收益率和止损距离。

#### Scenario: 仪表盘包含当前持仓
- **WHEN** 用户请求 `GET /api/dashboard`
- **THEN** 每项派生字段与持仓 API 中同一快照一致

#### Scenario: 存在已关闭持仓
- **WHEN** 组合包含 `closed` 持仓
- **THEN** 它们计入已实现汇总，但不计入当前敞口列表

### Requirement: Today's alert summary
系统 SHALL 按 Asia/Shanghai 自然日边界返回今日告警数和最新告警快照。

#### Scenario: 今日存在告警
- **WHEN** 当前上海自然日内创建过告警
- **THEN** 仪表盘返回告警数量和最新一条快照

#### Scenario: 今日没有告警
- **WHEN** 当前上海自然日内没有告警
- **THEN** 今日告警数为零，最新告警为 null

### Requirement: Frontend dashboard layout
前端 SHALL 以风险优先的层级展示仪表盘：首先呈现组合风险和待处理告警，其次呈现总盈亏、市值与成本摘要，最后呈现按止损距离排序的活动持仓和紧凑的今日告警摘要；布局 SHALL 根据视口宽度重排而不产生页面级横向滚动。

#### Scenario: 桌面端加载成功
- **WHEN** 用户在至少 1024px 宽的视口打开仪表盘且请求成功
- **THEN** 页面先显示风险摘要，再显示资产指标、持仓概览和今日告警，并直接展示需要处理的告警数量

#### Scenario: 手机端加载成功
- **WHEN** 用户在 360px 到 767px 宽的视口打开仪表盘且请求成功
- **THEN** 摘要以不超过两列的结构排列，持仓使用适合窄屏的完整摘要卡片，页面不出现横向滚动

#### Scenario: 存在临近止损持仓
- **WHEN** 多个活动持仓具有不同的止损距离
- **THEN** 持仓概览按止损距离从近到远排列，并使临近或已触发项具有明确的非颜色风险提示

#### Scenario: 今日没有告警
- **WHEN** 今日告警数为零且最新告警为 null
- **THEN** 页面使用紧凑状态提示表达暂无告警，不保留大面积空白告警面板

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
仪表盘 API SHALL 从新仓位领域模型计算开放市值、剩余成本、净已实现/未实现盈亏、风险金额和估值覆盖率，并以 Decimal 安全表示返回。

#### Scenario: Active and closed positions coexist
- **WHEN** 组合同时包含开放、部分平仓和关闭仓位
- **THEN** 开放指标只使用剩余数量，已实现指标包含全部 allocation，二者不得重复计算

#### Scenario: Quote coverage is incomplete
- **WHEN** 部分开放仓位没有可行动行情
- **THEN** API 返回降低的覆盖率并明确实时汇总未覆盖的仓位数量

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

