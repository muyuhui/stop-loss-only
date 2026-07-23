# Stop-Loss Engine

## Purpose

Calculate stop-loss prices and detect triggers using three methods: fixed price, percentage, and trailing (moving) stop-loss.
## Requirements
### Requirement: Calculate fixed-price stop-loss
系统 SHALL 使用十进制定点运算，按配置价格精度计算并保存固定价格止损线。

#### Scenario: 计算固定止损价
- **WHEN** 买入价为 `10.00`，方式为 `fixed`，止损值为 `9.00`
- **THEN** 止损价等于十进制值 `9.00`

#### Scenario: 固定止损价高于买入价
- **WHEN** 买入价为 `10.00`，固定止损值为 `11.00`
- **THEN** 系统返回校验错误，因为止损价必须低于买入价

### Requirement: Calculate percentage stop-loss
系统 SHALL 使用十进制定点运算和统一舍入规则，按 `buy_price × (1 - stop_loss_value / 100)` 计算百分比止损价。

#### Scenario: 百分之十止损
- **WHEN** 买入价为 `10.00`，方式为 `percentage`，止损值为 `10`
- **THEN** 止损价等于 `9.00`

#### Scenario: 百分比超出范围
- **WHEN** 百分比不在 1 至 99 的闭区间内
- **THEN** 系统返回校验错误

### Requirement: Calculate trailing stop-loss
系统 SHALL 基于最高的新鲜有效行情使用十进制定点运算计算移动止损线，并保证同一持仓生命周期内止损线不下降。

#### Scenario: Initial trailing stop-loss at buy price
- **WHEN** holding has buy_price=10.00, highest_price=10.00 (just bought), method="trailing", stop_loss_value=10
- **THEN** stop_loss_price SHALL equal 9.00

#### Scenario: Trailing stop-loss rises with price
- **WHEN** holding has buy_price=10.00, highest_price=18.00, method="trailing", stop_loss_value=10
- **THEN** stop_loss_price SHALL equal 16.20

#### Scenario: Trailing stop-loss never decreases even if price drops
- **WHEN** holding has highest_price=18.00, but current_price drops to 17.00
- **THEN** stop_loss_price remains at 16.20 (based on highest_price, not current_price)

#### Scenario: 新鲜行情创出新高
- **WHEN** 活动持仓最高价为 `15.00`，收到新鲜有效现价 `16.00`
- **THEN** 系统先把最高价更新为 `16.00`，再计算移动止损线

#### Scenario: 过期行情高于历史最高价
- **WHEN** 失败或过期行情的数值高于已记录最高价
- **THEN** 最高价和移动止损线均不变化

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

### Requirement: Confirm stop-loss closure
系统 SHALL 要求用户显式操作，才能把 `triggered` 持仓改为 `closed`，并把实际平仓价与触发价分开记录。

#### Scenario: 用户确认已平仓
- **WHEN** 用户为 `triggered` 持仓提交有效平仓价
- **THEN** 状态变为 `closed`，并记录实际平仓价

#### Scenario: 触发后尚未确认
- **WHEN** 止损线已触发但用户尚未确认平仓
- **THEN** 持仓保持 `triggered`，不得计为已成交退出

### Requirement: Update highest price for trailing stop
The system SHALL update highest_price whenever current_price exceeds the existing highest_price for trailing stop holdings.

#### Scenario: New high reached
- **WHEN** holding has highest_price=15.00, current_price=16.00, method="trailing"
- **THEN** highest_price SHALL be updated to 16.00

#### Scenario: Price below highest
- **WHEN** holding has highest_price=15.00, current_price=14.00
- **THEN** highest_price remains 15.00

### Requirement: Rearm a triggered position explicitly
系统 SHALL 只允许对开放且风险状态为 `triggered` 或 `acknowledged` 的仓位提交新止损规则、非空人工原因和预期版本来重新布防，并创建新触发序列。

#### Scenario: Rearm with valid new rule
- **WHEN** 用户提交有效新规则、原因和当前版本
- **THEN** 系统原子停用旧规则、启用新规则、将风险状态设为 `normal` 并追加不可变事件

#### Scenario: New rule is already breached
- **WHEN** 当前可行动行情已低于新止损价
- **THEN** 系统拒绝静默恢复并返回需要明确确认的稳定风险错误

### Requirement: Acknowledge risk separately from alert reading
系统 SHALL 将风险确认记录为仓位风险状态和不可变事件，且不得改变告警阅读状态或删除原触发事实。

#### Scenario: Acknowledge triggered risk
- **WHEN** 用户确认已知悉触发风险
- **THEN** 风险状态变为 `acknowledged`，告警阅读状态保持原值

