## ADDED Requirements

### Requirement: Rearm a triggered position explicitly
系统 SHALL 允许用户为已触发仓位提交新止损规则和人工原因重新布防，创建不可变风险覆盖和规则事件，并开始新的触发序列。

#### Scenario: Rearm with a valid new rule
- **WHEN** 用户为 `triggered` 或 `triggered_acknowledged` 仓位提交有效新规则和非空原因
- **THEN** 系统激活新规则、状态回到 `holding`，并保留旧告警与旧规则快照

#### Scenario: Rearm without a reason
- **WHEN** 用户未提供人工覆盖原因
- **THEN** 系统返回 422 且仓位、规则和事件均不变化

#### Scenario: Old quote is below the new stop
- **WHEN** 重新布防时最后行情已低于新止损价
- **THEN** 系统要求用户再次明确确认即时风险，并只在新的可行动行情或明确确认策略下产生新触发

### Requirement: Acknowledge risk separately from reading an alert
系统 SHALL 区分告警阅读状态与仓位风险确认状态，风险确认必须记录操作者、时间和可选备注，但不得改变止损触发事实。

#### Scenario: Mark alert as read
- **WHEN** 用户仅把告警标记已读
- **THEN** 告警阅读状态更新，仓位仍保持原触发状态且不创建风险确认事件

#### Scenario: Acknowledge triggered risk
- **WHEN** 用户确认已经知晓触发风险
- **THEN** 仓位变为 `triggered_acknowledged` 并创建风险确认事件

## MODIFIED Requirements

### Requirement: Detect stop-loss trigger
系统 SHALL 用可行动的新鲜现价与十进制止损价比较；当现价小于等于止损价时，使用仓位版本条件原子地提交状态变化、触发事件和一个告警。触发不代表已经成交，响应只允许报告已经提交的触发。

#### Scenario: 新鲜行情跌破止损线
- **WHEN** `holding` 仓位收到可行动现价 `8.80`，止损价为 `9.00`
- **THEN** 状态原子地变为 `triggered`，创建一个事件和一个告警，并在提交后报告触发

#### Scenario: 现价恰好等于止损价
- **WHEN** 可行动现价按配置精度等于止损价
- **THEN** 仓位状态变为 `triggered`

#### Scenario: 价格高于止损线
- **WHEN** 可行动现价为 `10.50`，止损价为 `9.00`
- **THEN** 仓位保持 `holding`，且不创建触发事件或告警

#### Scenario: 不可行动行情低于止损价
- **WHEN** `unpriced`、`stale`、`error` 或策略禁止的 `close` 行情数值低于止损价
- **THEN** 仓位不变化，也不创建触发事件或告警

#### Scenario: 重复判断同一触发序列
- **WHEN** 调度器重试或并发刷新再次处理同一规则的已触发仓位
- **THEN** 版本条件和幂等约束阻止重复事件与告警，响应反映数据库已提交事实

#### Scenario: One concurrent transaction loses the race
- **WHEN** 两个周期同时尝试触发同一仓位且一个条件更新失败
- **THEN** 失败周期重新读取已提交状态，不回滚其他标的结果，也不报告未提交的新触发
