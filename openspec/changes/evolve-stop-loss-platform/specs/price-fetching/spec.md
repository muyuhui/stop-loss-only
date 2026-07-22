## ADDED Requirements

### Requirement: Expose explicit quote states
系统 SHALL 把每个提供方结果规范化为 `unpriced`、`live`、`delayed`、`close`、`nav`、`stale` 或 `error`，并返回来源、行情时间、抓取时间、新鲜截止时间和是否可用于止损判断。

#### Scenario: Position has never received a quote
- **WHEN** 新建持仓尚未成功取得真实行情
- **THEN** 行情状态为 `unpriced`，买入价占位不得标记为实时或用于触发

#### Scenario: Market is closed
- **WHEN** 手动刷新取得最近交易日收盘价
- **THEN** 行情状态为 `close`，响应明确市场休市且不得伪装为 `live`

#### Scenario: Quote exceeds freshness policy
- **WHEN** 行情时间超过对应资产的新鲜度策略
- **THEN** 状态为 `stale` 且 `is_actionable=false`

### Requirement: Isolate fixture providers from the network
fixture 行情与日历适配器 SHALL 完全由注入数据决定，并且不得导入、调用或等待真实网络提供方。

#### Scenario: Run offline smoke test
- **WHEN** 必选冒烟测试配置 fixture 行情和固定市场时钟
- **THEN** 价格刷新在本地确定性完成且任何网络调用会立即使测试失败

### Requirement: Bound provider calls
生产行情适配器 SHALL 对日历和行情调用设置明确总超时、缓存、有限重试和熔断状态，并使用稳定错误码隐藏外部异常细节。

#### Scenario: Full-market dataset times out
- **WHEN** 全市场数据集在总超时前未返回
- **THEN** 本轮相关标的返回 `provider_timeout`，其他独立数据集仍可继续处理

#### Scenario: Calendar cache is valid
- **WHEN** 同一市场和日期已有有效交易日历缓存
- **THEN** 后续监控周期复用缓存且不重复调用外部日历接口

## MODIFIED Requirements

### Requirement: Scheduled price monitoring
系统 SHALL 在有效交易时段按配置间隔运行统一监控周期，使用可注入交易日历决定市场状态，并且只使用成功、状态可行动且满足对应资产新鲜度策略的行情更新仓位与判断止损；每个周期 SHALL 持久化诊断结果。

#### Scenario: 收到新鲜可行动行情
- **WHEN** 定时周期收到状态为 `live`、`delayed` 或符合策略的 `nav` 行情
- **THEN** 系统保存行情元数据、更新适用的最高价并判断止损

#### Scenario: 收到失败、未取价或过期行情
- **WHEN** 行情状态为 `error`、`unpriced` 或 `stale`
- **THEN** 系统报告对应状态，不更新最高价，也不产生新止损触发

#### Scenario: 非交易时段触发调度任务
- **WHEN** 调度任务在无效交易时段触发
- **THEN** 任务保存 `skipped` 周期且不调用行情提供方

#### Scenario: 交易日历降级
- **WHEN** 外部日历失败但存在有效缓存或允许的工作日退化结果
- **THEN** 周期标记 `calendar_degraded` 并继续强制交易时段限制

### Requirement: Manual price refresh API
系统 SHALL 提供统一手动监控刷新接口，支持可选标的或仓位范围，并返回周期 ID、市场状态、聚合数量、逐标的行情状态和已提交的新触发仓位；休市行情 SHALL 明确标记其状态和默认触发策略。

#### Scenario: 全部刷新成功
- **WHEN** 所有请求标的都成功处理
- **THEN** 响应标识周期并逐项给出行情状态、新鲜度、来源和已提交触发结果

#### Scenario: 部分刷新成功
- **WHEN** 部分行情提供方或标的失败
- **THEN** 响应标记 `partial`，保留成功更新，并列出失败标的稳定错误码

#### Scenario: 没有活动持仓
- **WHEN** 请求范围内没有需要行情的活动仓位
- **THEN** 响应成功，请求数和处理数均为零，fixture 模式不得访问任何外部服务

#### Scenario: 休市时取得收盘价
- **WHEN** 用户在休市时手动刷新并取得最近收盘价
- **THEN** 响应标记 `market_open=false` 与 `quote_state=close`，默认不把它声称为实时触发

#### Scenario: 监控周期整体失败
- **WHEN** 内部错误导致统一监控周期无法产生有效结果
- **THEN** API 返回适当 5xx、稳定错误码和关联 ID，不得声称价格已刷新
