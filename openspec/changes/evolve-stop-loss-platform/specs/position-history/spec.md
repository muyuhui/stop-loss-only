## ADDED Requirements

### Requirement: Preserve immutable position events
系统 SHALL 为建仓、加仓、规则启用、止损触发、风险确认、重新布防、部分平仓、全部平仓和元数据变更创建带版本 payload 的不可变事件。

#### Scenario: Stop rule is changed
- **WHEN** 用户为活动仓位启用一个新止损规则
- **THEN** 系统创建 `rule_activated` 事件并保留旧规则及旧事件不变

#### Scenario: Position is rearmed after trigger
- **WHEN** 用户提交新规则和人工原因完成重新布防
- **THEN** 系统依次记录风险覆盖和新规则事件，旧触发事件仍可查询

#### Scenario: User deletes a business record
- **WHEN** 用户删除允许删除的仓位
- **THEN** 系统软删除业务对象但继续保留事件和告警审计历史

### Requirement: Store bounded quote and stop-line history
系统 SHALL 保存系统实际取得的规范化行情快照和当时有效止损线，并按配置保留时间管理历史。

#### Scenario: Fresh quote is applied
- **WHEN** 新鲜行情参与一次仓位估值或止损判断
- **THEN** 系统保存行情状态、来源、行情时间、抓取时间、周期 ID 和有效止损线

#### Scenario: Failed quote attempt
- **WHEN** 提供方返回失败且没有价格
- **THEN** 系统在周期诊断中记录失败，但不创建伪造的价格历史点

#### Scenario: History expires
- **WHEN** 历史点早于配置保留时间
- **THEN** 系统分批清理旧点且不可删除关联的触发事件快照

### Requirement: Query chart and timeline history efficiently
系统 SHALL 提供分页事件时间线和有界图表序列，图表响应包含价格、止损线、规则变更、触发和平仓标记，并且单次最多返回 1000 个下采样点。

#### Scenario: Query a one-year chart
- **WHEN** 一年范围包含超过 1000 个行情点
- **THEN** 系统下采样至不超过 1000 点并保留窗口内的触发和规则变更关键点

#### Scenario: Query event timeline
- **WHEN** 用户按页查询仓位事件
- **THEN** 系统按创建时间和 ID 稳定倒序返回事件及分页元数据
