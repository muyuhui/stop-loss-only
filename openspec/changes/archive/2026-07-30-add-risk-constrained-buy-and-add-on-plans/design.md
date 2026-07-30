## Context

当前稳定运行时只支持 `legacy` 和 `shadow-read`，两者都以 `Holding` 为唯一可写组合事实。仓库已有 `risk_budget_summary`、新仓风险数量计算、风险设置字段和规划器页面，但后端只聚合 `Position`，能力策略也只在不受稳定运行时支持的 `new-authoritative` 阶段开放这些接口。前端还把风险试算与 Position 创建能力绑定，因此即使计算本身是只读的，稳定用户也无法使用。

Holding 已保存数量、买入价、当前止损价、生命周期和行情可信状态，足以按止损发生时的账面损失计算风险上限，但不保存历史交易费用或批次。第一版必须接受这一边界，不能为了加仓试算提前开启 Position 生命周期写入、迁移权威模型或伪造费用精度。

## Goals / Non-Goals

**目标：**

- 在 `legacy` 与 `shadow-read` 稳定运行面提供可解释、只读的新仓买入和 Holding 加仓风险试算。
- 让风险预算始终只读取当前权威模型，并在 shadow-read 中避免重复计算投影数据。
- 使用后端 Decimal 计算和稳定拒绝原因，保留未知值和覆盖缺口，不输出虚假建议数量。
- 加仓试算保留现有止损价，通过组合容量和单笔容量共同约束增量数量。
- 将试算与任何业务写入能力解耦，在前端清楚表达“最大风险承受数量”而不是投资标的推荐。

**非目标：**

- 判断标的质量、预测涨跌、生成技术或基本面信号、维护观察列表或执行回测。
- 连接券商、读取真实现金、预留风险额度、自动下单或确认实际成交。
- 修改 Holding 数量/成本/止损，创建第二笔 Holding，或启用 Position 创建、批次、部分平仓、确认和重新布防。
- 迁移到 `new-authoritative`、改变 readiness 边界或增加数据库表/列。
- 为 legacy 历史持仓补造费用、税费或批次信息。

## Decisions

### 使用权威模型适配器生成统一风险事实

把数据库读取与风险公式分开。风险预算服务先根据 `authority(db).stage` 选择唯一适配器，输出内部统一的风险事实，例如记录 ID、资产类型、生命周期、数量、成本、止损价、当前风险和覆盖状态；纯计算层只消费这些事实。

- `legacy`、`shadow-read`：只查询 `Holding.status in {holding, triggered}`，风险为 `max(0, (buy_price - stop_loss_price) * quantity)`；`closed` 不参与，shadow Position 不参与。
- `new-authoritative`：保留现有 Position、剩余成本、剩余数量和活动 StopRule 计算。
- 任一活动权威记录无法生成风险事实时，返回覆盖小计，但将组合剩余容量设为不可确定。

拒绝同时查询 Holding 与 Position 后按代码去重，因为代码相同不代表同一业务记录，也无法可靠识别投影与独立仓位。显式按 authority 选源更容易测试和审计。

### 复用纯 Decimal 数量引擎，但区分新仓与加仓容量

新仓继续使用现有公式：

```text
position_limit = portfolio_equity * effective_position_risk_pct
allowed_risk = min(position_limit, remaining_portfolio_capacity)
raw_quantity = (allowed_risk - entry_fees - estimated_exit_fees)
               / (entry_price - initial_stop_price)
```

加仓需要先扣除当前 Holding 已占用的单笔风险：

```text
current_holding_risk = max(0, (buy_price - existing_stop_price) * quantity)
remaining_position_capacity = max(0, position_limit - current_holding_risk)
allowed_incremental_risk = min(
  remaining_position_capacity,
  remaining_portfolio_capacity,
)
raw_quantity = (
  allowed_incremental_risk - entry_fees - estimated_exit_fees
) / (planned_entry_price - existing_stop_price)
```

A 股按 100 股向下取整，基金按六位小数向下取整。取整后重新计算增量预计损失、加仓后持仓风险、组合已用风险、使用率和所需资金。所有响应财务值继续使用 Decimal 字符串。

拒绝只按组合剩余容量计算加仓，因为这可能让单个 Holding 超过单笔风险上限。也拒绝按当前市值或浮盈增加容量，因为风险政策使用手工组合权益和止损损失，而不是行情驱动的杠杆额度。

### 加仓永远沿用现有止损价

加仓请求只接受 `holding_id`、计划成交价、计划买入费用、预计退出费用和可选单笔风险比例，不接受新止损方式或新止损值。单位风险使用计划价减现有持久化止损价；计划价小于或等于止损价时拒绝试算。

这样可以避免用户通过试算自动降低止损来制造更多“可用容量”，也不会重置移动止损的最高价。调整止损仍必须通过原有独立流程，并在调整后重新试算。

拒绝按加仓后的加权成本重算百分比止损，因为这会隐式改变现有风险规则；也拒绝在第一版为每个 legacy Holding 引入批次止损，因为那等同于提前实现 Position 域。

### 提供独立的只读加仓试算 API

保留 `POST /api/risk/plans/preview` 作为新仓买入试算，并让它按当前 authority 读取风险预算。新增 `POST /api/risk/plans/add-on-preview`，请求包含 `holding_id` 和计划参数。

加仓响应除通用规划字段外，返回只读 Holding 快照、现有止损价、当前持仓风险、剩余单笔容量、允许增量风险、增量预计损失、试算后持仓风险、试算后组合风险与使用率。成功和拒绝响应使用同一结构，无法安全计算的字段返回 `null`。

两个端点均不执行 `commit`、`flush` 或投影操作。测试在调用前后比较所有业务表记录数和关键字段，而不只验证 HTTP 方法看似只读。

### 将风险试算能力与写入能力彻底解耦

在 `legacy` 和 `shadow-read` 策略中启用 `risk_budget_reads` 与 `risk_plan_previews`，继续关闭 `risk_covered_position_creation` 和 `position_lifecycle_writes`。`new-authoritative` 的隔离 API 行为保持现状，但稳定 readiness 仍拒绝该阶段。

前端规划器只以 `risk_plan_previews` 判断是否允许试算；创建 Position 的确认区域继续额外要求 `risk_covered_position_creation`。因此稳定运行面会显示风险设置、风险预算和规划器，但不会出现 Position 或批次写入命令。

拒绝新增一个几乎同义的 `legacy_risk_plan_previews` 能力，因为试算契约本身可以做到权威模型无关；真正需要分开的边界是只读试算与业务写入。

### 使用独立模式呈现新仓与加仓试算

规划器提供“新仓试算”和“加仓试算”两个模式。新仓模式保留现有输入；加仓模式由 Holding 详情通过可恢复 URL 上下文进入，并加载只读 Holding 风险摘要。只有可行动行情可以预填计划价格；未定价、收盘、陈旧或错误行情均保持输入为空。

结果主标题使用“风险约束下的最大数量”。加仓结果同时展示加仓前后持仓风险和组合风险；页面固定显示不是标的推荐、收益预测或下单指令。稳定运行面只提供重新试算和返回持仓操作，不提供“确认创建仓位”或“记录加仓”。

## Risks / Trade-offs

- [legacy Holding 不含历史费用，组合已用风险可能低估实际退出成本] -> 明确 legacy 风险口径只包含成本与止损价；计划自身费用完整计入增量风险，不补造历史费用。
- [用户可能把“最大数量”理解为应该买满] -> 使用“风险上限”语义，同时展示较小数量同样有效，不使用“推荐买入”或收益导向文案。
- [试算后组合或设置可能变化] -> 每次试算读取最新数据库快照，展示试算时间，并声明不预留容量；用户采取行动前需要重新试算。
- [手工计划价与真实成交价不同] -> 结果明确回显输入价格；只有可行动行情允许预填，实际成交后风险必须重新评估。
- [加仓保持止损可能与用户策略预期不同] -> 在表单和结果中突出“沿用现有止损价”，需要改变止损时引导先走独立止损编辑流程再试算。
- [能力开启会让风险设置和仪表盘区域重新出现] -> 后端预算 API 必须先支持 legacy 权威事实；组件测试覆盖能力可用、权益未设置、覆盖不完整和请求失败状态。
- [shadow-read 双源造成重复风险] -> 适配器只按 authority 选择 Holding，集成测试使用一一对应的 shadow 数据证明结果不翻倍。

## Migration Plan

1. 抽取权威风险事实适配器和纯 Decimal 计算函数，保持现有 Position 测试通过，并补充 legacy/shadow-read 风险预算测试。
2. 扩展新仓预览、增加加仓预览 schema/API 和稳定拒绝原因，证明所有路径零写入。
3. 调整能力策略与前端功能开关，先让预算和只读试算可见，再增加规划器模式与 Holding 详情入口。
4. 更新冻结契约、README、真实组件和三个视口 E2E，运行完整离线验证及严格 OpenSpec 校验。

不需要数据库迁移。回滚时恢复旧代码即可；所有试算均未写入业务数据，已有风险设置与数据库仍兼容。

## Open Questions

无。将试算结果写回 Holding、以独立 Holding 记录实际加仓、启用 Position 批次，以及标的信号/回测均留给后续独立 change。
