## ADDED Requirements

### Requirement: 重新布防标记告警处置状态
重新布防动作 SHALL 在处置该持仓的同时，把该持仓 `disposition` 为 `triggered` 或空的待处理告警标记为 `rearmed`，MUST 保持阅读状态不变，MUST NOT 标记已关闭或已重新布防的告警；`GET /api/alerts` 的 `disposition` 筛选 SHALL 支持按 `rearmed` 查询。待处理告警卡 SHALL 提供直达对应持仓处置页的入口（主操作"去处置"）。

#### Scenario: 重新布防后待处理告警标记
- **WHEN** 用户对已触发持仓执行重新布防
- **THEN** 该持仓全部 `disposition` 为 `triggered` 或空的告警变为 `rearmed`，阅读状态不变，已关闭告警不受影响

#### Scenario: 按处置状态筛选重新布防
- **WHEN** 用户以 `disposition=rearmed` 筛选告警
- **THEN** 只返回已重新布防的告警

#### Scenario: 待处理告警提供处置入口
- **WHEN** 告警卡处置状态为 `triggered`
- **THEN** 卡片提供主操作"去处置"直达对应持仓处置页；其他处置状态提供"查看持仓"
