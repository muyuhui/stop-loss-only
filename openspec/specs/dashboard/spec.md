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

### Requirement: 展示已实现盈亏
仪表盘资产摘要 SHALL 展示后端返回的毛已实现盈亏，并与未实现盈亏明确区分；无已关闭持仓时显示真实零值，未知或不可用数值不得显示为虚假结果。

#### Scenario: 存在已关闭持仓
- **WHEN** 组合包含 `closed` 持仓且后端返回已实现盈亏
- **THEN** 资产摘要展示毛已实现盈亏金额（可为正或负），并明确与未实现盈亏区分

#### Scenario: 没有已关闭持仓
- **WHEN** 组合不存在 `closed` 持仓
- **THEN** 资产摘要显示已实现盈亏为零，不显示为未知占位

#### Scenario: 移动端布局
- **WHEN** 用户在 360px 到 767px 宽的视口查看资产摘要
- **THEN** 已实现盈亏随摘要以不超过两列的网格重排，页面不产生横向滚动

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

### Requirement: 展示交易时段与行情时效
仪表盘 SHALL 呈现交易时段徽标（`pre_market`/`open`/`lunch`/`closed` 映射为 盘前/交易中/午休/已收盘，来源为 `/api/monitoring/status` 的 `market_session`）与持仓行情时效（口径与持仓列表一致）；时段指示 MUST 只表达时间语义，不判定节假日，且 MUST NOT 影响任何监控或触发行为。行情不可用时 MUST 不显示时效或年龄。

#### Scenario: 盘中展示交易中
- **WHEN** `/api/monitoring/status` 返回 `market_session` 为 `open`
- **THEN** 仪表盘显示"交易中"徽标，且与覆盖率、监控状态同区域展示

#### Scenario: 午休或收盘展示对应徽标
- **WHEN** `/api/monitoring/status` 返回 `lunch` 或 `closed`
- **THEN** 仪表盘显示"午休"或"已收盘"徽标

#### Scenario: 行情时效随持仓展示
- **WHEN** 持仓概览包含拥有可估值行情的活动持仓
- **THEN** 对应卡片显示与持仓列表同一口径的时效文本；未定价持仓不显示时效

#### Scenario: 状态不可用时降级
- **WHEN** `/api/monitoring/status` 请求失败或 `market_session` 缺失
- **THEN** 仪表盘不显示时段徽标且不出现错误，其余监控信息正常呈现

### Requirement: 待处置持仓队列
仪表盘 SHALL 在存在 `triggered` 持仓时展示"待处置持仓"队列：列出每笔已触发持仓（名称/代码、当前价与止损价、状态标签）并提供"去处置"直达对应详情页的入口；没有已触发持仓时 MUST 不渲染该区域。队列数据 MUST 与仪表盘既有载荷同源（`triggered_count` 与持仓列表），MUST NOT 发起额外请求。

#### Scenario: 存在已触发持仓
- **WHEN** 组合中存在 `triggered` 持仓
- **THEN** 仪表盘在风险区后展示待处置队列，每项可直达 `/holdings/:id` 处置页

#### Scenario: 没有已触发持仓
- **WHEN** 组合中不存在 `triggered` 持仓
- **THEN** 仪表盘不渲染待处置区域，其余内容不受影响

### Requirement: 返回本月账本聚合
`GET /api/dashboard` SHALL 在响应中返回 `month_summary` 聚合，包含：`month`（当前月份标签 `YYYY-MM`，Asia/Shanghai 月界）、`realized_profit_loss`（本月已实现盈亏）、`closed_count`（本月平仓笔数）、`triggered_count`（本月触发告警数）、`stop_adjustment_count` 与 `stop_lowered_count`（本月止损调整总次数与其中调低次数）、`largest_loss`（当前最大浮亏来源或 null）。既有响应字段 MUST 保持不变，空组合返回零值而非 null 聚合。

#### Scenario: 返回本月已实现盈亏与平仓笔数
- **WHEN** 用户请求 `GET /api/dashboard` 且本月存在已平仓持仓（成本、平仓价、数量可计算）
- **THEN** `month_summary.realized_profit_loss` 等于本月平仓 `(平仓价 − 买入价) × 数量` 之和，`closed_count` 等于本月平仓笔数

#### Scenario: 上月平仓不计入本月
- **WHEN** 存在上月平仓的持仓且本月无平仓
- **THEN** `month_summary.realized_profit_loss` 为 0 且 `closed_count` 为 0

#### Scenario: 返回本月触发与止损调整统计
- **WHEN** 本月存在触发告警与来源为 `update`/`rearm` 的止损调整记录
- **THEN** `triggered_count` 等于本月告警数，`stop_adjustment_count` 等于本月调整数，`stop_lowered_count` 只统计调整后止损价低于该持仓上一条历史记录的次数

#### Scenario: 返回最大浮亏来源
- **WHEN** 当前存在可估值的浮亏持仓
- **THEN** `largest_loss` 返回其中浮亏金额最大的名称、代码与负值浮亏额

#### Scenario: 无浮亏时最大亏损来源为空
- **WHEN** 所有可估值持仓均浮盈或无可估值持仓
- **THEN** `largest_loss` 为 null

#### Scenario: 空组合返回零值聚合
- **WHEN** 不存在任何持仓
- **THEN** `month_summary` 各计数为 0、`realized_profit_loss` 为 0、`largest_loss` 为 null，`month` 为当前 `YYYY-MM`

### Requirement: 展示本月账本卡片
前端仪表盘 SHALL 在行情可信摘要之后、待处置队列之前展示"本月账本"卡片：主导数字为本月已实现盈亏（按盈亏语义着色），副标题为平仓笔数；辅助行展示本月触发次数、止损调整次数（含调低次数）与当前浮亏参考（明确标注为当前快照）；`largest_loss` 非空时展示最大亏损来源；存在待处置项时提供"去处置"行动入口。卡片 MUST 与 `month_summary` 使用同一时区口径展示月份标签；`month_summary` 缺失或为空时 MUST 不渲染卡片；空组合显示零值。

#### Scenario: 展示本月已实现盈亏
- **WHEN** 用户打开仪表盘且响应包含 `month_summary`
- **THEN** 卡片主导数字显示本月已实现盈亏并按盈亏着色，副标题显示平仓笔数

#### Scenario: 展示触发与调整统计
- **WHEN** 本月存在触发或止损调整记录
- **THEN** 卡片辅助行显示本月触发次数与调整次数（含调低次数）

#### Scenario: 展示最大亏损来源
- **WHEN** `largest_loss` 非空
- **THEN** 卡片显示最大亏损来源的名称与浮亏金额

#### Scenario: 提供待处置行动入口
- **WHEN** 仪表盘存在待处置（已触发）持仓
- **THEN** 卡片提供"去处置"入口并导向告警或处置页面；无待处置时不显示入口

#### Scenario: 卡片数值与接口一致
- **WHEN** 用户刷新仪表盘
- **THEN** 卡片展示的本月已实现盈亏等数值与 `GET /api/dashboard` 的 `month_summary` 一致

#### Scenario: 空组合显示零值
- **WHEN** 不存在任何持仓
- **THEN** 卡片显示零值账本（本月已实现盈亏 0、计数 0），不显示虚假金额

