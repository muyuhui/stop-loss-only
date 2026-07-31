# AI Holding Reviews

## Purpose

为受支持运行面提供用户主动触发、基于可信近期行情和权威风险事实的 DeepSeek 单持仓复盘，同时确保模型建议受确定性规则约束且不产生业务写入。

## Requirements

### Requirement: 按需复盘单个活动持仓
系统 SHALL 为 stable legacy 与 shadow-read 运行面的 `holding` 或 `triggered` Holding 提供用户主动触发的 DeepSeek 单持仓复盘，并 MUST NOT 为已关闭 Holding、shadow Position 投影或不受支持的新权威运行面生成复盘。

#### Scenario: 复盘持有中的 Holding
- **WHEN** 用户在支持 AI 复盘的运行面请求复盘一个状态为 `holding` 的权威 Holding
- **THEN** 系统使用该 Holding 的最新权威事实准备复盘，而不读取对应 shadow Position 作为第二份持仓

#### Scenario: 复盘已触发 Holding
- **WHEN** 用户请求复盘一个状态为 `triggered` 的 Holding
- **THEN** 系统允许解释该持仓，但最终建议动作保持为执行既定止损，不得由模型改写为继续持有或加仓

#### Scenario: 拒绝已关闭持仓
- **WHEN** 用户请求复盘状态为 `closed` 的 Holding
- **THEN** 系统返回稳定拒绝原因 `holding_not_active`，且不调用 DeepSeek

#### Scenario: 拒绝不受支持的权威阶段
- **WHEN** 当前数据库处于不受稳定运行面支持的 `new-authoritative`
- **THEN** AI 复盘 API 返回能力不可用，且不读取 Position 冒充 legacy Holding 复盘

### Requirement: 在复盘前取得可信当前行情
前端 SHALL 将“更新行情并 AI 复盘”作为一个可理解的分阶段操作，先通过现有目标持仓行情刷新流程更新权威事实，再重新读取 Holding 并请求 AI 复盘。AI review API MUST NOT 自行运行监控周期；直接请求时若当前行情不可用于复盘，系统 SHALL 返回稳定的数据未就绪状态。

#### Scenario: 刷新成功后开始复盘
- **WHEN** 用户触发复盘且目标持仓行情刷新成功
- **THEN** 前端重新读取刷新后的 Holding，并使用该权威版本请求 AI 复盘

#### Scenario: 刷新触发既有止损规则
- **WHEN** 前置行情刷新根据现有监控规则更新最高价、止损状态或创建告警
- **THEN** 这些变更作为用户明确发起的行情刷新结果正常提交，随后 AI 只能解释已提交事实

#### Scenario: 当前行情未就绪
- **WHEN** review API 读取到目标 Holding 的行情状态为 `unpriced`、`stale` 或 `error`
- **THEN** 系统返回 `market_data_not_ready`，不调用 DeepSeek，也不把买入成本或零值作为当前行情

#### Scenario: 使用非实时但可估值行情
- **WHEN** 当前行情是具有可信来源和时间的 `close`、`nav` 或受支持延迟行情
- **THEN** 系统允许复盘，并在快照与结果中明确其非实时状态和行情时间

### Requirement: 准备独立的近期行情分析窗口
系统 SHALL 为 AI 复盘读取当前市场日期前 90 个自然日内、最多最新 60 个有效交易日的收盘价或基金净值，且分析窗口 MUST NOT 因 Holding 买入日期较晚而截断。系统 SHALL 复用规范化行情来源和 `price_history` 技术缓存，并返回样本数、来源、最后交易日、缓存是否降级以及行情点。

#### Scenario: 新买入持仓包含买入前行情
- **WHEN** Holding 买入日期为昨天但缓存或提供方存在此前 90 天行情
- **THEN** AI 分析窗口包含买入日前的有效行情，而现有持仓历史图表语义保持不变

#### Scenario: 历史缺口补齐成功
- **WHEN** 90 天窗口的缓存存在可识别缺口且行情提供方返回有效数据
- **THEN** 系统规范化并补齐 `price_history` 缓存，按日期升序选取最多最新 60 个有效点

#### Scenario: 提供方失败但缓存足够
- **WHEN** 历史更新失败，但缓存仍覆盖最近有效交易日且至少有 20 个有效点
- **THEN** 系统允许降级复盘，明确使用缓存、最后交易日和更新警告

#### Scenario: 历史样本不足
- **WHEN** 可用历史行情少于 20 个有效点但至少有一个点
- **THEN** 系统只允许低可信的持仓与止损风险复盘，不得生成近期趋势结论，并明确样本不足

#### Scenario: 完全没有历史行情
- **WHEN** 缓存和行情提供方均不能提供任何有效历史点
- **THEN** 系统返回 `history_data_unavailable`，不调用 DeepSeek

### Requirement: 由后端确定性生成复盘事实
系统 SHALL 使用 Decimal 安全或等价的确定性计算生成版本化事实快照，包含持仓状态、行情可信度、持有期结果、止损状态、近期区间指标、该持仓风险和聚合组合风险。5 日、20 日和 60 日收益、最大回撤及相对区间高低点位置 MUST 由后端计算；样本不足的指标 SHALL 返回不可用而不是零，DeepSeek MUST NOT 成为任何数值字段的权威来源。

#### Scenario: 指标样本完整
- **WHEN** 最近行情具有足够的 60 日比较点
- **THEN** 快照返回后端计算的 5 日、20 日和 60 日收益、最大回撤、区间位置及对应稳定事实标识

#### Scenario: 长周期样本不足
- **WHEN** 行情只有 25 个有效点
- **THEN** 5 日和 20 日指标按实际数据计算，60 日指标明确不可用且不显示为 `0%`

#### Scenario: 组合风险覆盖不完整
- **WHEN** 风险预算只能返回覆盖小计而不能确定剩余容量
- **THEN** 快照明确记录覆盖缺口和剩余容量未知，最终结果不得把该状态描述为仍有加仓空间

#### Scenario: shadow-read 不重复计算风险
- **WHEN** shadow-read 同时存在 legacy Holding 和对应 shadow Position
- **THEN** 复盘事实中的持仓风险和组合风险只使用一次 legacy 权威事实

### Requirement: 通过 DeepSeek Provider 生成受限结构化结果
系统 SHALL 将版本化事实快照交给内部 `AIProvider` 契约，并在第一版仅注册 DeepSeek Provider。Provider 结果 MUST 通过严格结构校验，包含简短结论、受限动作、最多三项带有效事实引用的依据、最多两项风险情景、数据局限和 `high`、`medium` 或 `low` 可信程度。

#### Scenario: DeepSeek 返回有效结构
- **WHEN** DeepSeek 返回字段完整、枚举合法且所有事实引用均存在于当前快照的结果
- **THEN** 后端使用当前快照中的权威显示值构造最终中文复盘响应，并返回模型标识与生成时间

#### Scenario: DeepSeek 引用不存在的事实
- **WHEN** DeepSeek 返回快照中不存在的事实标识或无法验证的数字依据
- **THEN** 系统返回 `ai_response_invalid`，不展示原始模型文本或虚构依据

#### Scenario: DeepSeek 返回禁止动作
- **WHEN** DeepSeek 请求自动下单、修改止损、直接写入加仓数量或返回契约外动作
- **THEN** 结构校验拒绝响应并返回 `ai_response_invalid`

#### Scenario: 后续 Provider 扩展
- **WHEN** 后续实现另一个符合相同输入输出契约的 Provider
- **THEN** 持仓快照、公开 review API 和前端结果结构无需因供应商协议变化而修改

### Requirement: 限制 AI 建议的含义和优先级
最终建议动作 SHALL 仅允许 `execute_existing_stop`、`pause_add_on`、`continue_observing`、`review_risk_exposure`、`open_add_on_preview` 或 `refresh_data`。确定性状态 MUST 覆盖模型倾向；界面 SHALL 说明复盘只分析近期价格行为和风险，不包含新闻、财报、投资价值或收益预测，也不是交易指令。

#### Scenario: 已触发止损覆盖模型输出
- **WHEN** 权威 Holding 状态为 `triggered`，但 Provider 返回其他允许动作
- **THEN** 最终响应将动作固定为 `execute_existing_stop`，并引用已触发事实

#### Scenario: 风险条件不允许进入加仓试算
- **WHEN** 风险覆盖不完整、剩余容量未知或运行时不支持风险试算
- **THEN** 最终响应不得包含 `open_add_on_preview`，即使 Provider 返回该动作

#### Scenario: 可以进入加仓试算
- **WHEN** Provider 返回 `open_add_on_preview`，风险覆盖完整、容量为正且只读加仓试算能力可用
- **THEN** 界面只提供进入现有风险试算的入口，并明确该动作不等于推荐加仓且不包含建议数量

#### Scenario: 不具备基本面数据
- **WHEN** 用户查看任意成功复盘
- **THEN** 结果明确列出未使用新闻、财报、行业研究、券商资金和未来价格预测

### Requirement: 隔离模型失败并保护敏感数据
系统 SHALL 对未配置、并发占用、超时、限流、不可用和无效响应提供稳定错误码，并 MUST NOT 在客户端错误、应用日志、诊断包或数据库中记录 API Key、Authorization、完整事实快照、Prompt、原始模型响应、持仓价格、数量或成本。DeepSeek 失败 MUST NOT 影响核心持仓与监控工作流。

#### Scenario: 尚未配置 DeepSeek
- **WHEN** 用户或客户端请求复盘但本机没有 DeepSeek API Key
- **THEN** 系统返回 `ai_not_configured`，不发起外部请求，并提供进入设置页的可恢复路径

#### Scenario: DeepSeek 超时或限流
- **WHEN** Provider 请求超过有界总超时或收到限流响应
- **THEN** 系统分别返回 `ai_timeout` 或 `ai_rate_limited`，保留原有持仓页面数据并允许用户重试

#### Scenario: 同一持仓重复提交
- **WHEN** 同一进程中一个 Holding 已有进行中的复盘，客户端再次提交
- **THEN** 系统返回 `ai_review_busy`，不重复发送包含持仓事实的 Provider 请求

#### Scenario: 复盘完成后检查业务事实
- **WHEN** AI 复盘成功、失败或响应无效
- **THEN** Holding、Position、批次、止损规则、事件、告警、设置和订单相关事实均不因 review API 改变，只有近期行情准备所需的 `price_history` 技术缓存可以更新

### Requirement: 在持仓详情展示可追溯复盘
持仓详情页 SHALL 在 AI 能力可用时提供复盘入口，并在请求期间展示刷新当前行情、补齐历史行情和生成复盘的可理解阶段。成功结果 SHALL 展示建议动作、结论、事实依据、风险情景、数据局限、可信程度、当前行情时间、历史最后交易日、生成时间和模型标识，且 MUST 以纯文本渲染模型内容。

#### Scenario: 完成一次复盘
- **WHEN** 用户从活动 Holding 详情成功完成行情刷新和 DeepSeek 复盘
- **THEN** 页面在不遮挡现有止损操作的区域展示完整结构化结果，并允许重新复盘

#### Scenario: 页面离开后结果不持久化
- **WHEN** 用户离开详情页后再次进入或持仓事实已更新
- **THEN** 旧 AI 结果不被宣称为当前有效复盘，用户需要主动重新生成

#### Scenario: 手机端复盘
- **WHEN** 用户在 360px 到 767px 宽视口生成或查看复盘
- **THEN** 阶段状态、建议、依据、局限和重试操作按单列完整显示，不产生页面级横向滚动且不遮挡持仓操作
