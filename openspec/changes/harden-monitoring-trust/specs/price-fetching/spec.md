## ADDED Requirements

### Requirement: Expose explicit quote states
系统 SHALL 把提供方结果规范化为 `unpriced`、`live`、`delayed`、`close`、`nav`、`stale` 或 `error`，并返回来源、行情时间、抓取时间、新鲜截止时间和是否可用于止损判断。

#### Scenario: Position has never received a quote
- **WHEN** 新持仓只有买入成本占位值
- **THEN** 行情状态为 `unpriced` 且 `is_actionable=false`

#### Scenario: Market is closed
- **WHEN** 休市时手动刷新取得最近收盘价
- **THEN** 行情状态为 `close`，响应不得把它表示为实时行情或默认自动触发依据

### Requirement: Isolate fixture providers from the network
系统 SHALL 通过可注入的行情提供方和交易日历端口运行 fixture 模式，fixture 模式 MUST NOT 导入、解析或调用任何真实行情、日历、DNS 或 socket API。

#### Scenario: Run offline smoke test
- **WHEN** 网络哨兵开启且系统使用 fixture provider 和 fixture calendar
- **THEN** 完整刷新与触发流程成功且没有任何外部网络调用

### Requirement: Bound provider calls
系统 SHALL 为外部行情和日历调用设置连接与总超时，并在同一周期内让同一全市场数据集最多下载一次。

#### Scenario: Provider times out
- **WHEN** 提供方超过硬超时
- **THEN** 系统返回稳定错误码、记录脱敏诊断，并继续处理不依赖该结果的标的

## MODIFIED Requirements

### Requirement: Scheduled price monitoring
系统 SHALL 按运行时设置的间隔对活动持仓执行价格监控，只将状态为 `live`、`delayed` 或符合资产策略的 `nav` 行情用于更新和止损判断，并记录周期结果。

#### Scenario: 收到新鲜可行动行情
- **WHEN** 定时周期收到可行动行情
- **THEN** 系统持久化行情元数据、更新兼容最新价并执行止损判断

#### Scenario: 收到失败、未取价或过期行情
- **WHEN** 行情状态为 `unpriced`、`stale` 或 `error`
- **THEN** 系统保留最后成功事实、记录失败且不触发止损

#### Scenario: 非交易时段触发调度任务
- **WHEN** 日历明确市场休市
- **THEN** 周期记录跳过或收盘状态，不伪装成实时成功

### Requirement: Manual price refresh API
系统 SHALL 提供手动刷新 API，返回周期 ID、成功/失败计数、稳定错误详情和仅包含已提交触发的结果，并支持按标的或持仓限定范围。

#### Scenario: 部分刷新成功
- **WHEN** 一部分标的成功而另一部分失败
- **THEN** API 返回部分成功、已提交事实和逐标的稳定错误，不回滚成功标的

#### Scenario: 没有活动持仓
- **WHEN** 系统没有需要刷新的活动持仓
- **THEN** API 成功返回空结果和完成的周期摘要
