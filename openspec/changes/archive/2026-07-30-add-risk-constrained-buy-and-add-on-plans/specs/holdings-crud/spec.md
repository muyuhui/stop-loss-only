## ADDED Requirements

### Requirement: 从持仓详情发起加仓风险试算
前端 SHALL 在运行时支持只读风险试算时，为状态为 `holding` 的 Holding 提供“加仓风险试算”入口。入口 SHALL 携带稳定 Holding 标识进入独立试算上下文，展示现有数量、成本、止损价和风险作为只读事实，并要求用户明确输入计划成交价和费用。

#### Scenario: 活动持仓进入加仓试算
- **WHEN** 用户从状态为 `holding` 的持仓详情激活“加仓风险试算”
- **THEN** 页面加载该 Holding 的当前风险上下文，保留其止损价，并且在用户提交计划参数前不计算或写入数量

#### Scenario: 可行动行情预填计划价格
- **WHEN** Holding 具有可行动当前行情
- **THEN** 页面可以用该行情预填计划成交价，同时明确显示行情状态并允许用户修改计划价格

#### Scenario: 行情不可用或不可行动
- **WHEN** Holding 未定价或只有不可行动行情
- **THEN** 计划成交价保持为空并要求用户明确输入，页面不得使用买入成本或陈旧价格伪装当前计划价

#### Scenario: 已触发或已关闭持仓
- **WHEN** 用户查看 `triggered` 或 `closed` Holding
- **THEN** 页面不展示可执行的加仓试算入口，并继续优先展示处置或历史事实

#### Scenario: 运行时不支持风险试算
- **WHEN** `risk_plan_previews=false`
- **THEN** 持仓详情不展示加仓试算入口，现有查看、止损修改和手动平仓流程保持不变
