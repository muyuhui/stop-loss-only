## ADDED Requirements

### Requirement: Report monitoring trust on the dashboard
仪表盘 SHALL 返回调度器状态、最近监控周期、最近成功时间、可行动行情数量、过期/失败数量和估值覆盖率，并且不依赖外部行情源即时可用才能读取。

#### Scenario: One quote is stale
- **WHEN** 四个活动仓位中一个行情过期
- **THEN** 仪表盘返回三个可行动、一个过期和对应估值覆盖率

#### Scenario: Latest cycle is partial
- **WHEN** 最近周期部分成功
- **THEN** 页面显示降级状态、失败数量和进入诊断的操作，同时保留最后成功数据

### Requirement: Calculate portfolio stop-risk metrics
系统 SHALL 计算高风险仓位金额、止损风险金额、预计止损损失、仓位权重和行情覆盖口径，并按已提交仓位快照返回。

#### Scenario: Position approaches stop
- **WHEN** 活动仓位当前价接近止损价
- **THEN** 仪表盘返回该仓位风险金额、预计止损损失和组合权重

#### Scenario: Quote is not actionable
- **WHEN** 某仓位没有可行动行情
- **THEN** 该仓位不混入实时风险总额，并在缺失估值计数中体现

## MODIFIED Requirements

### Requirement: Portfolio summary
系统 SHALL 将活动仓位的剩余成本、可覆盖市值和未实现收益，与关闭分配产生的净已实现收益分开计算，并返回生命周期数量、费用、估值覆盖率和数据口径。

#### Scenario: 同时存在活动、部分关闭和已关闭仓位
- **WHEN** 组合包含多个生命周期及费用税费
- **THEN** 系统分别计算剩余成本、覆盖市值、未实现收益、净已实现收益、费用和状态数量

#### Scenario: 部分仓位缺少可行动行情
- **WHEN** 活动仓位中存在 `unpriced`、`stale` 或 `error` 行情
- **THEN** 汇总明确返回估值覆盖率和缺失数量，不把成本占位伪装为实时市值

#### Scenario: 没有持仓
- **WHEN** 组合为空
- **THEN** 所有金额和状态数量为零，估值覆盖率使用明确的空组合语义

### Requirement: Frontend dashboard layout
前端 SHALL 按“监控可信度、需要行动的风险、组合指标、风险仓位、今日事件”顺序展示仪表盘，并根据视口重排而不产生页面级横向滚动。

#### Scenario: 桌面端加载成功
- **WHEN** 用户在至少 1024px 宽视口打开仪表盘
- **THEN** 首屏直接显示监控状态、触发数量、预计止损损失、估值覆盖率和风险最高仓位

#### Scenario: 手机端加载成功
- **WHEN** 用户在 360px 到 767px 宽视口打开仪表盘
- **THEN** 监控状态使用紧凑条，指标不超过两列，风险持仓使用可展开卡片且底部导航不遮挡内容

#### Scenario: 所有行情健康且没有风险
- **WHEN** 监控健康、行情完整且没有临近或触发仓位
- **THEN** 风险摘要保持紧凑，不使用占据大面积首屏的安全色块

#### Scenario: 数据持续未更新
- **WHEN** 最近成功周期早于预期间隔两倍
- **THEN** 页面保留最后数据但明确标记过期，并提供刷新和诊断入口
