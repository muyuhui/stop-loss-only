# Price Fetching

## Purpose

Fetch real-time A-share stock prices and fund NAV values via akshare, with scheduled monitoring on trading days.

## Requirements

### Requirement: Fetch real-time stock price
The system SHALL fetch the current real-time price for an A-share stock using akshare.

#### Scenario: Fetch stock price during trading hours
- **WHEN** system calls the price fetcher for code "000001" during trading hours
- **THEN** system returns current price, change percentage, and timestamp

#### Scenario: Fetch stock price outside trading hours
- **WHEN** system calls the price fetcher outside trading hours
- **THEN** system returns the last available closing price

### Requirement: Fetch fund NAV
The system SHALL fetch the latest net asset value (NAV) for a fund using akshare.

#### Scenario: Fetch ETF fund price
- **WHEN** system calls price fetcher for a fund with type "fund" and code "510050"
- **THEN** system returns the latest available price or NAV

#### Scenario: Fetch off-exchange fund NAV
- **WHEN** system calls price fetcher for an off-exchange fund
- **THEN** system returns the latest published NAV (may be T or T-1 day)

### Requirement: Batch fetch prices for all holdings
系统 SHALL 在每个监控周期内，每类全市场数据最多抓取一次、每个资产类型与代码组合的单品数据最多抓取一次，并把结果应用到所有匹配的活动持仓。

#### Scenario: 批量刷新多笔持仓
- **WHEN** 监控周期请求 `000001`、`510050` 和 `159915` 的行情
- **THEN** 系统返回每笔持仓的结果，且不会为每笔持仓重复下载同一市场数据集

#### Scenario: 多笔持仓使用相同代码
- **WHEN** 两笔活动持仓具有相同资产类型和代码
- **THEN** 同一条行情分别应用到两笔持仓

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

#### Scenario: Calendar uses weekday fallback
- **WHEN** 权威交易日历不可用、没有有效缓存且系统使用工作日启发式降级
- **THEN** 系统可以取价并记录 `weekday_fallback` 诊断，但默认设置 `is_actionable=false`；只有提供方行情自身包含可验证的当前交易日和当前交易时段时间时才允许触发

### Requirement: Trading day detection
系统 SHALL 把行情提供方的日历值统一为日期，并使用 Asia/Shanghai 时区判断 A 股交易时段。

#### Scenario: 当前处于交易时段
- **WHEN** 日历标记当天开市，且本地时间位于 09:30–11:30 或 13:00–15:00
- **THEN** 定时监控允许执行

#### Scenario: 当前不处于交易时段
- **WHEN** 当天休市或时间不在两个交易时段内
- **THEN** 定时监控跳过行情抓取和止损判断，并记录原因

#### Scenario: 交易日历获取失败
- **WHEN** 无法获取交易日历
- **THEN** 系统使用已记录的工作日退化规则、标记本轮为 degraded，并继续强制交易时段限制

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
- **WHEN** 没有 `holding` 或 `triggered` 需要行情
- **THEN** 响应成功，请求数和处理数均为零
