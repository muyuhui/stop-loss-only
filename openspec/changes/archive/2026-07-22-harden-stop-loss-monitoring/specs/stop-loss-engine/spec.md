## MODIFIED Requirements

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

#### Scenario: 新鲜行情创出新高
- **WHEN** 活动持仓最高价为 `15.00`，收到新鲜有效现价 `16.00`
- **THEN** 系统先把最高价更新为 `16.00`，再计算移动止损线

#### Scenario: 过期行情高于历史最高价
- **WHEN** 失败或过期行情的数值高于已记录最高价
- **THEN** 最高价和移动止损线均不变化

### Requirement: Detect stop-loss trigger
系统 SHALL 用新鲜有效现价与十进制止损价比较；当现价小于等于止损价时，原子地把状态从 `holding` 改为 `triggered` 并创建一个告警。触发不代表已经成交。

#### Scenario: 新鲜行情跌破止损线
- **WHEN** `holding` 持仓收到新鲜现价 `8.80`，止损价为 `9.00`
- **THEN** 状态变为 `triggered`，并且只创建一个告警

#### Scenario: 现价恰好等于止损价
- **WHEN** 新鲜现价按配置精度等于止损价
- **THEN** 持仓状态变为 `triggered`

#### Scenario: 失败或过期行情低于止损价
- **WHEN** 失败或过期行情的数值低于止损价
- **THEN** 持仓不变化，也不创建告警

#### Scenario: 重复判断同一触发
- **WHEN** 已为 `triggered` 的同一生命周期再次执行判断
- **THEN** 不创建重复告警

### Requirement: Confirm stop-loss closure
系统 SHALL 要求用户显式操作，才能把 `triggered` 持仓改为 `closed`，并把实际平仓价与触发价分开记录。

#### Scenario: 用户确认已平仓
- **WHEN** 用户为 `triggered` 持仓提交有效平仓价
- **THEN** 状态变为 `closed`，并记录实际平仓价

#### Scenario: 触发后尚未确认
- **WHEN** 止损线已触发但用户尚未确认平仓
- **THEN** 持仓保持 `triggered`，不得计为已成交退出
