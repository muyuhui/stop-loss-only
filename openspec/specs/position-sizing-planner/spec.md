# Position Sizing Planner

## Purpose

Provide an explainable, read-only position-sizing preview from entry price, stop rule, fees, portfolio capacity, and asset quantity rules before a separately confirmed position creation.

## Requirements

### Requirement: Preview position size without business writes
系统 SHALL 根据当前权威阶段提供只读新仓买入风险试算：在 `legacy` 或 `shadow-read` 阶段读取活动 Holding 的风险预算，在隔离的 `new-authoritative` 阶段读取开放 Position 的风险预算。试算 SHALL 读取生效风险政策和当前已覆盖组合风险，计算建议数量，并且不写入 Holding、Position、批次、规则、事件、告警、设置、行情、导入或投递记录。

#### Scenario: 在 legacy 稳定运行面试算新仓
- **WHEN** 用户提交完整有效的新仓计划，legacy Holding 风险覆盖完整且仍有风险容量
- **THEN** 系统返回计算结果和规范化输入，不改变任何业务记录数量或内容

#### Scenario: 在 shadow-read 稳定运行面试算新仓
- **WHEN** 用户在 `shadow-read` 阶段提交新仓计划
- **THEN** 系统只从 legacy Holding 权威事实计算一次风险，不把 shadow Position 重复计入组合风险

#### Scenario: 在隔离的新权威阶段试算
- **WHEN** 数据库处于 `new-authoritative` 且调用受支持的隔离风险 API
- **THEN** 系统继续从 Position 事实计算风险，且预览本身不创建仓位或其他业务记录

### Requirement: Calculate risk-sized quantity deterministically
The system SHALL use Decimal arithmetic to calculate the initial stop with an existing supported stop method, use the lesser of the per-position limit and remaining portfolio capacity, subtract explicit estimated entry and exit fees, divide by positive entry-to-stop unit risk, and round quantity down to the asset increment. It SHALL recompute projected loss and required capital from the rounded quantity and return every formula input and limiting value as Decimal strings.

#### Scenario: A-share quantity rounds to a board lot
- **WHEN** raw risk-sized quantity is `495` shares for an A-share
- **THEN** recommended quantity is `400`, and projected risk is recomputed from `400`

#### Scenario: Fund quantity preserves supported precision
- **WHEN** a fund plan produces a positive fractional raw quantity
- **THEN** recommended quantity is rounded down to six fractional places without binary floating-point conversion

#### Scenario: Fees consume part of the risk limit
- **WHEN** allowed plan risk is `1000`, estimated entry and exit fees total `10`, entry price is `20`, and initial stop is `18`
- **THEN** the raw quantity is calculated from `(1000 - 10) / 2` before asset-increment rounding

#### Scenario: Trailing stop is previewed
- **WHEN** the user selects the existing trailing percentage rule
- **THEN** the planner uses entry price as the initial high-water mark and returns the resulting initial stop explicitly

### Requirement: Refuse misleading recommendations
系统 MUST NOT 在组合权益未设置、当前权威组合的止损风险覆盖不完整、剩余容量为零、费用耗尽允许风险、止损价不低于计划买入价、数量取整后为零或必填输入无效时返回建议数量。系统 SHALL 返回稳定原因码及仍可安全展示的部分解释，并 MUST NOT 用 shadow 投影补齐或重复计算权威风险。

#### Scenario: legacy 组合覆盖不完整
- **WHEN** 任一活动 Holding 缺少可计算的数量、成本或有效止损价
- **THEN** 新仓和加仓试算均不返回建议数量，并标识组合风险覆盖不完整

#### Scenario: Position 组合覆盖不完整
- **WHEN** 新权威组合的已用风险只是覆盖小计，因为一个开放 Position 缺少可计算止损
- **THEN** 试算不返回建议数量，并标识组合风险覆盖不完整

#### Scenario: 止损价不低于计划买入价
- **WHEN** 新仓计划的初始止损价等于或高于计划买入价
- **THEN** 试算不返回数量，并标识单位风险不是正数

#### Scenario: 数量向下取整后为零
- **WHEN** A 股取整前数量不足一个 100 股交易单位
- **THEN** 试算不返回数量，并说明可用风险无法支持最小买入单位

### Requirement: Explain advisory scope and required capital
前端 SHALL 展示风险上限、组合容量、费用假设、单位风险、取整前数量、风险约束下的最大数量、预计止损损失、所需资金及试算后的风险占用。界面 SHALL 明确说明结果只回答风险承受能力，不判断标的质量或上涨概率，不是收益预测、下单指令或风险额度预留；系统不知道券商可用现金，也没有提交订单。

#### Scenario: 展示可执行的新仓试算
- **WHEN** 有效新仓计划返回正数建议数量
- **THEN** 界面在展示风险计算明细和所需资金时，将结果命名为“风险约束下的最大数量”而不是“推荐买入”

#### Scenario: 展示可执行的加仓试算
- **WHEN** 有效加仓计划返回正数建议数量
- **THEN** 界面同时展示加仓前后该持仓风险、组合风险占用、保留的止损价和预计所需资金

#### Scenario: 所需资金超过用户实际现金
- **WHEN** 用户查看系统无法通过券商余额验证的试算结果
- **THEN** 界面不声称用户买得起，并要求用户独立核对可用资金

### Requirement: Hand off a reviewed plan to position creation
前端 SHALL 仅在新权威运行面同时声明 `risk_plan_previews` 和 `risk_covered_position_creation` 时，允许有效新仓试算预填受风险约束的 Position 创建流程。legacy/shadow-read 稳定运行面 SHALL 保持试算只读且不调用任何写入 API，但 SHALL 对有效新仓试算结果提供“填入新增持仓”入口：将规范化输入和向下取整后的推荐数量预填到稳定持仓新增表单，用户必须独立复核并显式提交后才创建 Holding；页面 MUST NOT 声称试算结果已预留风险容量，MUST NOT 显示 Position 创建、Holding 自动写入或自动记录加仓操作。

#### Scenario: 新权威阶段继续创建仓位
- **WHEN** 运行时同时允许风险试算和受风险约束的 Position 创建，且用户选择继续
- **THEN** Position 表单预填代码、资产类型、名称、价格、数量、费用和止损配置，但在用户独立复核并提交前不创建仓位

#### Scenario: 稳定运行面填入新增持仓
- **WHEN** legacy 或 shadow-read 用户取得有效新仓试算结果并选择“填入新增持仓”
- **THEN** 稳定持仓新增表单预填代码、名称、资产类型、按资产精度处理的买入价、整数数量、默认买入日期和止损配置，页面不调用任何写入 API，用户显式提交后走正常稳定持仓创建流程

#### Scenario: 稳定运行面基金数量取整
- **WHEN** 有效新仓试算的推荐数量不是整数
- **THEN** 预填数量向下取整为整数份，并在表单中明确提示数量已按持仓整数单位取整、可自行调整

#### Scenario: 稳定运行面加仓结果保持只读
- **WHEN** legacy 或 shadow-read 用户取得加仓试算结果
- **THEN** 页面只展示计算结果和重新试算操作，不提供新增持仓或其他写入入口

#### Scenario: 试算在提交前过期
- **WHEN** 支持创建的运行面在试算后发生组合数据或设置变化
- **THEN** 正常创建校验仍为权威结果，界面不得声称先前试算已经预留风险容量

### Requirement: 只读试算现有持仓的加仓数量
系统 SHALL 对状态为 `holding` 且具有可计算现有止损风险的 legacy Holding 提供只读加仓试算。试算 SHALL 保留现有止损价，以单笔风险上限扣除该持仓当前风险后的余额和组合剩余风险容量两者中的较小值作为增量风险上限，扣除明确费用后按计划价格与现有止损价之间的单位风险计算并向下取整建议数量。

#### Scenario: 现有持仓仍有单笔与组合风险容量
- **WHEN** 活动持仓当前预计止损损失为 `400`，单笔风险上限为 `1000`，组合剩余容量为 `800`，计划价格为 `10`，现有止损价为 `9`，增量费用为 `10`
- **THEN** 本次允许增量风险为 `600`，取整前数量按 `(600 - 10) / (10 - 9)` 计算，并按资产数量单位向下取整

#### Scenario: 加仓不改变现有止损事实
- **WHEN** 用户试算一个百分比或移动止损 Holding 的加仓数量
- **THEN** 结果使用当前持久化止损价，不重算止损百分比、不降低止损价、不重置最高价或移动止损高水位

#### Scenario: 计划价格不高于现有止损价
- **WHEN** 用户提交的计划成交价小于或等于当前止损价
- **THEN** 系统不返回建议数量，并返回稳定原因 `entry_not_above_existing_stop`

#### Scenario: 持仓不允许加仓试算
- **WHEN** Holding 已处于 `triggered` 或 `closed`，或当前止损风险无法计算
- **THEN** 系统不返回建议数量，并返回对应的稳定拒绝原因

#### Scenario: 加仓试算没有业务写入
- **WHEN** 任意加仓试算成功或被拒绝
- **THEN** Holding、Position、批次、止损规则、事件、告警、设置和行情记录均保持不变
