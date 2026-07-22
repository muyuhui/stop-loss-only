## ADDED Requirements

### Requirement: Represent positions using transaction lots
系统 SHALL 以一个或多个 Decimal 交易批次表示仓位，每个批次记录数量、剩余数量、单位成本、交易日期、费用和税费，汇总剩余数量 MUST 等于所有活动批次剩余数量之和。

#### Scenario: Add another lot
- **WHEN** 用户向开放仓位增加合法批次
- **THEN** 系统原子保存批次并重新计算剩余数量和成本

#### Scenario: Import fractional fund quantity
- **WHEN** 基金批次包含资产精度允许的小数份额
- **THEN** 系统不通过二进制浮点转换而精确保留数量

### Requirement: Support FIFO partial and complete close accounting
系统 SHALL 使用 FIFO 将平仓数量分配到活动批次，并记录平仓价格、时间、费用、税费、净收入和已实现盈亏；首轮 MUST NOT 允许运行时切换成本方法。

#### Scenario: Partially close a multi-lot position
- **WHEN** 平仓数量小于总剩余数量
- **THEN** 系统按 FIFO 保存 allocation，仓位保持 `lifecycle_status=open`，部分平仓事实由 allocation 和剩余数量推导

#### Scenario: Close remaining quantity
- **WHEN** 平仓数量等于总剩余数量
- **THEN** 系统将生命周期设为 `closed`、保存关闭时间并停止监控

### Requirement: Calculate portfolio values with explicit coverage
系统 SHALL 在后端计算已实现盈亏、未实现盈亏、仓位权重、止损风险金额、预计止损损失和可行动行情估值覆盖率，并以 Decimal 安全格式返回。

#### Scenario: One position has no actionable quote
- **WHEN** 组合中一个开放仓位没有可行动行情
- **THEN** 实时组合指标排除该估值并降低覆盖率，响应明确缺口
