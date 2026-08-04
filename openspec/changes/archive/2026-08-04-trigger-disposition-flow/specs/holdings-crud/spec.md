## ADDED Requirements

### Requirement: 重新布防已触发持仓
系统 SHALL 提供 `POST /api/holdings/{id}/rearm` 供 `triggered` 持仓重新布防：校验新止损规则并在同一事务内保存新规则、重算止损价、状态回到 `holding`、递增触发序列与版本、写入来源为 `rearm` 的止损调整历史、把待处理告警标记为 `rearmed`。非 `triggered` 状态 MUST 返回 400；校验失败 MUST 返回 422 且不改变任何状态；既有 `PUT /holdings/{id}` 仅 `holding` 可修改的契约 MUST 保持不变。

#### Scenario: 触发后重新布防
- **WHEN** 用户为 `triggered` 持仓提交有效的新止损规则
- **THEN** 持仓状态回到 `holding`，保存新规则与重算止损价，历史写入来源 `rearm`，待处理告警标记 `rearmed`

#### Scenario: 重新布防校验失败
- **WHEN** 提交的规则组合校验失败
- **THEN** 返回 422，状态、止损规则、历史与告警均不变化

#### Scenario: 非触发状态布防被拒
- **WHEN** 用户对 `holding` 或 `closed` 持仓调用 rearm
- **THEN** 返回 400，持仓不变化

#### Scenario: 详情页处置引导
- **WHEN** 用户打开 `triggered` 持仓详情
- **THEN** 页面将止损编辑入口呈现为"重新布防"（保存走 rearm），并保留手动平仓入口；布防成功后刷新状态与历史时间线
