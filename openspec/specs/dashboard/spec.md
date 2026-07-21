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
The frontend SHALL display the dashboard as a grid with: portfolio summary cards at top, holdings table in middle, and alert summary at bottom.

#### Scenario: Dashboard loads successfully
- **WHEN** user navigates to the dashboard page
- **THEN** the page displays summary cards, a holdings table with real-time prices, and today's alert summary

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
