## ADDED Requirements

### Requirement: Return Decimal-safe portfolio accounting summaries
仪表盘 API SHALL 从新仓位领域模型计算开放市值、剩余成本、净已实现/未实现盈亏、风险金额和估值覆盖率，并以 Decimal 安全表示返回。

#### Scenario: Active and closed positions coexist
- **WHEN** 组合同时包含开放、部分平仓和关闭仓位
- **THEN** 开放指标只使用剩余数量，已实现指标包含全部 allocation，二者不得重复计算

#### Scenario: Quote coverage is incomplete
- **WHEN** 部分开放仓位没有可行动行情
- **THEN** API 返回降低的覆盖率并明确实时汇总未覆盖的仓位数量
