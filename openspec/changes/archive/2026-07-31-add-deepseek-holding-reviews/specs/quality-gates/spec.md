## ADDED Requirements

### Requirement: 离线验证 AI Provider 与结构化契约
强制后端测试 SHALL 使用可注入的 DeepSeek fixture 覆盖事实快照、近期行情窗口、Provider 请求、结构化响应校验、确定性覆盖和稳定错误映射，并 MUST 继续由网络哨兵阻断所有真实 DeepSeek、AkShare、DNS 和 socket 访问。

#### Scenario: 固定复盘成功
- **WHEN** fixture 提供已知 Holding、90 天行情、风险预算和合法 DeepSeek 结构化响应
- **THEN** 测试断言发送快照、后端指标、事实引用、最终动作、可信程度和时间元数据符合规格，且没有真实网络访问

#### Scenario: 新买入持仓的分析窗口
- **WHEN** fixture Holding 昨日买入但具有此前 90 天的缓存行情
- **THEN** 测试证明 AI 窗口包含买入前行情且现有持仓图表仍从买入日期开始

#### Scenario: Provider 异常矩阵
- **WHEN** fixture 分别模拟未配置、并发、超时、限流、不可用、非法 JSON、额外字段和无效事实引用
- **THEN** 每种情况返回对应稳定错误或 `ai_response_invalid`，且不泄露原始响应或密钥

### Requirement: 验证 AI 复盘的写入与隐私边界
强制测试 SHALL 对成功、拒绝和 Provider 失败路径比较复盘前后的核心业务事实，并检查应用日志、API 响应、诊断包和设置读取不包含密钥、Authorization、完整 Prompt、原始响应、持仓价格、数量或成本。

#### Scenario: review API 零业务写入
- **WHEN** review API 完成一次成功复盘和一次失败复盘
- **THEN** Holding、Position、批次、止损规则、事件、告警、设置和订单事实保持不变，只有明确的近期行情缺口准备可以改变 `price_history` 技术缓存

#### Scenario: 前置行情刷新保持既有语义
- **WHEN** 复盘用户流程先执行目标持仓行情刷新并触发既有止损条件
- **THEN** 测试证明刷新正常提交权威行情与告警，而随后 AI 请求不产生第二次触发或额外业务写入

#### Scenario: 密钥不进入持久化与日志
- **WHEN** 测试保存、替换、检测、使用和清除一个可识别 DeepSeek Key
- **THEN** SQLite、日志、诊断输出、API 响应和备份内容均找不到该明文值或 Authorization 头

### Requirement: 真实组件验证 AI 复盘体验
前端强制测试 SHALL 真实挂载 HoldingDetail、Settings、实际 router 和能力 store，覆盖 DeepSeek 未配置、分阶段加载、成功结果、确定性覆盖、失败重试、离开页面失效和重复提交保护。源码字符串断言 MUST NOT 作为这些行为的唯一证据。

#### Scenario: 未配置时进入设置
- **WHEN** `ai_holding_reviews=true` 且设置响应报告 DeepSeek 未配置
- **THEN** 持仓详情显示配置引导，用户可以进入设置页，且不会发起 review 请求

#### Scenario: 分阶段生成复盘
- **WHEN** 当前行情刷新、Holding 重读和 review API 依次成功
- **THEN** 组件按顺序展示刷新行情、补齐历史和生成复盘状态，期间阻止重复提交，最终展示结构化结果

#### Scenario: 已触发状态覆盖 AI 倾向
- **WHEN** review 响应基于已触发 Holding 返回 `execute_existing_stop`
- **THEN** 组件突出既有止损处置但不自动关闭持仓、不修改止损或调用加仓接口

### Requirement: 在目标视口验证 AI 设置与复盘
浏览器 E2E SHALL 在 `390x844`、`768x1024` 和 `1440x900` 使用构建前端、fixture 行情与 fixture DeepSeek 覆盖密钥配置状态、单持仓行情刷新、AI 复盘、失败重试和受限加仓试算入口，并检测横向溢出、固定导航遮挡、关键文本截断和未捕获浏览器错误。

#### Scenario: 三视口成功复盘
- **WHEN** 用户在每个目标视口为活动 Holding 运行一次成功复盘
- **THEN** 建议、依据、风险情景、数据局限、可信程度和数据时间完整可读，既有止损操作仍可访问且页面无横向溢出

#### Scenario: DeepSeek 不可用时继续核心流程
- **WHEN** fixture DeepSeek 返回超时或限流
- **THEN** 页面显示稳定失败与重试操作，持仓详情、行情信息、止损修改和手动平仓仍正常可用

#### Scenario: 加仓入口受确定性能力约束
- **WHEN** AI 动作为 `open_add_on_preview` 但运行时 fixture 关闭 `risk_plan_previews`
- **THEN** 浏览器页面不显示加仓试算命令，并明确 AI 结果不构成买入建议
