## ADDED Requirements

### Requirement: Expose trustworthy quote metadata on positions
持仓列表和详情 SHALL 返回行情状态、来源、行情时间、抓取时间、新鲜截止时间和是否可行动；尚未取得行情时 SHALL 明确标记 `unpriced`。

#### Scenario: Newly created position
- **WHEN** 新持仓创建后尚未刷新行情
- **THEN** 详情可返回成本占位用于表单上下文，但 `quote_state=unpriced` 且实时估值不可用

#### Scenario: Stale last quote
- **WHEN** 最后成功行情超过新鲜度策略
- **THEN** 列表和详情标记 `stale` 并返回最后行情时间

### Requirement: Add transaction lots to an active position
系统 SHALL 允许向活动仓位增加经过校验的交易批次，并原子地更新汇总数量、成本和相关派生值。

#### Scenario: Add valid lot
- **WHEN** 用户提交有效数量、成本、日期和费用
- **THEN** 新批次保存，仓位剩余数量和成本增加，并创建加仓事件

#### Scenario: Add lot to closed position
- **WHEN** 用户尝试向已关闭仓位增加批次
- **THEN** 系统返回 400 且不改变历史数据

### Requirement: Present closed positions as realized outcomes
前端 SHALL 对关闭仓位显示平仓价、关闭时间、净已实现盈亏、费用、持有天数和触发到平仓差异，并隐藏价格刷新和止损编辑操作。

#### Scenario: View closed position detail
- **WHEN** 用户打开状态为 `closed` 的仓位
- **THEN** 页面使用复盘布局且不显示“未实现盈亏”或活动止损操作

## MODIFIED Requirements

### Requirement: Manually close a holding
系统 SHALL 允许用户以有效数量、平仓价、平仓时间、费用和税费部分或全部关闭活动仓位，保存批次分配和净已实现盈亏；关闭操作不得额外创建止损告警。

#### Scenario: 手动部分关闭活动持仓
- **WHEN** 用户提交小于剩余数量的有效平仓数量
- **THEN** 系统保存平仓分配、已实现盈亏和事件，仓位保留剩余数量并变为 `partially_closed`

#### Scenario: 触发后确认全部关闭
- **WHEN** 用户为 `triggered` 仓位提交全部剩余数量和有效平仓价
- **THEN** 状态变为 `closed`、保存关闭时间，已有触发告警保持不变

#### Scenario: 手动关闭未触发仓位
- **WHEN** 用户为 `holding` 提交全部剩余数量和有效平仓信息
- **THEN** 状态变为 `closed`，记录平仓事件且不创建触发告警

#### Scenario: 重复关闭
- **WHEN** 用户尝试关闭没有剩余数量的 `closed` 仓位
- **THEN** 系统返回 400，仓位、批次和收益均不变化

#### Scenario: 平仓数量非法
- **WHEN** 数量小于等于零、超过剩余数量或违反标的精度
- **THEN** 系统返回 422 且不创建部分平仓记录
