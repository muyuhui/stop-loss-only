## ADDED Requirements

### Requirement: Represent positions using transaction lots
系统 SHALL 将一个标的仓位表示为一个或多个交易批次，每个批次使用十进制定点数量、单位成本、交易日期、费用、税费和剩余数量，并保证汇总剩余数量等于所有活动批次剩余数量之和。

#### Scenario: Create a position with one lot
- **WHEN** 用户为一个新标的录入首笔买入交易
- **THEN** 系统创建标的、仓位和一个剩余数量等于买入数量的交易批次

#### Scenario: Add another lot
- **WHEN** 用户向活动仓位增加一笔不同成本的买入交易
- **THEN** 系统保留两个独立批次并重新计算汇总数量与剩余成本

#### Scenario: Import fractional fund quantity
- **WHEN** 标的数量精度允许小数且用户导入有效小数份额
- **THEN** 系统不丢失数量精度并按标的精度保存

### Requirement: Support partial and complete close accounting
系统 SHALL 使用账户配置的成本匹配方法把平仓数量分配到活动批次，首轮默认 FIFO，并记录平仓价格、时间、费用、税费、净收入和已实现盈亏。

#### Scenario: Partially close a multi-lot position
- **WHEN** 用户平仓数量小于仓位剩余数量
- **THEN** 系统按 FIFO 分配数量、记录已实现盈亏并把仓位状态设为 `partially_closed`

#### Scenario: Close the remaining quantity
- **WHEN** 用户平仓数量等于仓位全部剩余数量
- **THEN** 系统把仓位设为 `closed`、保存关闭时间并停止止损监控

#### Scenario: Close more than remaining quantity
- **WHEN** 用户提交的平仓数量超过仓位剩余数量
- **THEN** 系统返回 422 且批次、收益和仓位状态均不变化

### Requirement: Calculate portfolio values with explicit coverage
系统 SHALL 分别计算净已实现盈亏、未实现盈亏、仓位权重、止损风险金额和预计止损损失，并返回使用可行动行情计算的估值覆盖率。

#### Scenario: All active positions have actionable quotes
- **WHEN** 所有活动仓位都有可行动行情
- **THEN** 估值覆盖率为 100%，仓位权重之和按舍入前数值等于 100%

#### Scenario: One position has no actionable quote
- **WHEN** 一个活动仓位行情为 `unpriced`、`stale` 或 `error`
- **THEN** 系统将其排除出实时估值覆盖分母并明确返回缺失估值数量

#### Scenario: Closed position detail
- **WHEN** 用户查询已关闭仓位
- **THEN** 响应以平仓分配计算净已实现盈亏，不再把当前价收益标记为未实现盈亏
