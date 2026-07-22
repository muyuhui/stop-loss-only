## ADDED Requirements

### Requirement: Track alert disposition separately from read state
告警 SHALL 分别记录阅读状态和处置状态，并关联触发事件、规则快照、仓位快照及后续确认、重新布防或平仓事件。

#### Scenario: Alert is read without disposition
- **WHEN** 用户只标记告警已读
- **THEN** 阅读状态改变，但处置状态和仓位风险状态不变

#### Scenario: Position is rearmed
- **WHEN** 用户成功重新布防
- **THEN** 原告警处置状态关联为 `rearmed`，原快照保持不可变
