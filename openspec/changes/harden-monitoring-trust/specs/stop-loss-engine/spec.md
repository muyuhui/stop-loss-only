## MODIFIED Requirements

### Requirement: Detect stop-loss trigger
系统 SHALL 仅用可行动的新鲜 Decimal 现价与止损价比较；当现价小于等于止损价时，使用版本条件和稳定幂等键原子提交状态变化与一个告警，响应只允许报告已提交触发。

#### Scenario: 新鲜行情跌破止损线
- **WHEN** 活动持仓收到可行动行情且现价低于止损价
- **THEN** 状态变化和告警在同一事务中提交一次

#### Scenario: 现价恰好等于止损价
- **WHEN** 可行动现价等于止损价
- **THEN** 系统提交一次触发和一次告警

#### Scenario: 不可行动行情低于止损价
- **WHEN** `unpriced`、`stale`、`error` 或策略禁止的 `close` 行情数值低于止损价
- **THEN** 系统不得改变持仓状态或创建告警

#### Scenario: 重复判断同一触发序列
- **WHEN** 同一规则和触发序列被重复判断
- **THEN** 系统最多保留一个已提交告警并返回数据库事实

#### Scenario: One concurrent transaction loses the race
- **WHEN** 两个周期并发尝试触发同一持仓且一个版本条件失败
- **THEN** 失败周期重新读取已提交状态，不报告未提交触发且不回滚其他标的
