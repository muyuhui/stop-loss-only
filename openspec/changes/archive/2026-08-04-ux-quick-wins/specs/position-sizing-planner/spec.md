## MODIFIED Requirements

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
