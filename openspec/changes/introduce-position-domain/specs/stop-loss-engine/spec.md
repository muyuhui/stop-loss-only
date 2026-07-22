## ADDED Requirements

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
