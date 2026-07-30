## MODIFIED Requirements

### Requirement: Aggregate covered portfolio stop risk
系统 SHALL 根据当前权威阶段聚合组合止损风险：`legacy` 与 `shadow-read` 阶段只读取状态为 `holding` 或 `triggered` 的 Holding，`new-authoritative` 阶段只读取开放 Position。legacy Holding 的预计止损损失 SHALL 使用 `max(0, (buy_price - stop_loss_price) * quantity)`；Position SHALL 继续使用剩余成本、剩余数量、活动止损规则和明确的预计退出成本。系统 SHALL 返回覆盖小计、组合上限、使用率、按记录数量与成本计算的覆盖率，以及已知剩余容量或明确的不可确定状态，并 MUST NOT 同时聚合权威事实与其 shadow 投影。

#### Scenario: legacy 组合风险覆盖完整
- **WHEN** 两个活动 Holding 均具有正数数量、买入价和有效止损价，预计止损损失合计为 `3800`，组合风险上限为 `5000`
- **THEN** 系统返回已用风险 `3800`、剩余容量 `1200`、完整 Holding 覆盖，且不计入对应 shadow Position

#### Scenario: legacy 已触发持仓仍占用风险
- **WHEN** 一个 Holding 已触发但尚未手动关闭
- **THEN** 系统继续把其止损风险计入组合风险，直至该 Holding 进入 `closed`

#### Scenario: legacy Holding 风险覆盖不完整
- **WHEN** 任一活动 Holding 缺少可计算的正数数量、买入价或止损价
- **THEN** 系统返回已覆盖小计和缺口，标记剩余容量不可确定，并阻止风险数量试算

#### Scenario: 所有开放 Position 都有止损覆盖
- **WHEN** 新权威组合权益为 `100000`、组合风险上限为 `5%`，且完全覆盖的开放 Position 预计止损损失合计为 `3800`
- **THEN** 系统返回上限 `5000`、已用风险 `3800`、使用率 `76.00` 和剩余容量 `1200`

#### Scenario: 组合风险上限已超过
- **WHEN** 当前权威模型中已覆盖的预计止损损失超过配置的组合上限
- **THEN** 系统返回零剩余容量、正数超出金额和超限状态

#### Scenario: 开放 Position 缺少活动止损
- **WHEN** 至少一个权威开放 Position 无法生成预计止损损失
- **THEN** 系统返回覆盖小计和降低后的覆盖率，将剩余容量标记为不可确定，且 MUST NOT 把小计表示为完整组合风险

#### Scenario: 当前行情不可用
- **WHEN** 权威活动记录具有有效成本、数量和止损价，但没有可行动当前行情
- **THEN** 其预计止损损失仍可被覆盖计算，当前估值覆盖率继续独立降级
