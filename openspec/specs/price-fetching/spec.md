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
系统 SHALL 在有效交易时段按配置间隔运行统一监控周期，并且只使用成功且满足对应资产新鲜度策略的行情判断止损。

#### Scenario: 收到新鲜行情
- **WHEN** 定时周期收到允许年龄内的成功行情
- **THEN** 系统记录行情元数据、更新适用的最高价并判断止损

#### Scenario: 收到失败或过期行情
- **WHEN** 行情抓取失败或行情年龄超过限制
- **THEN** 系统报告失败或过期状态，不更新最高价，也不产生新止损触发

#### Scenario: 非交易时段触发调度任务
- **WHEN** 调度任务在无效交易时段触发
- **THEN** 任务结束且不调用行情提供方

### Requirement: Manual price refresh API
系统 SHALL 将 `POST /api/prices/refresh` 作为统一监控周期的强类型响应，包含周期 ID、交易时段状态、聚合数量、逐标的行情状态和新触发持仓。

#### Scenario: 全部刷新成功
- **WHEN** 所有请求标的都成功处理
- **THEN** 响应标识本轮周期，并逐项给出成功、新鲜度和触发结果

#### Scenario: 部分刷新成功
- **WHEN** 部分行情提供方或标的失败
- **THEN** 响应标记部分成功，保留成功更新，并列出失败标的的结构化错误

#### Scenario: 没有活动持仓
- **WHEN** 没有 `holding` 或 `triggered` 需要行情
- **THEN** 响应成功，请求数和处理数均为零

#### Scenario: 监控周期整体失败
- **WHEN** 内部错误导致统一监控周期无法产生有效结果
- **THEN** API 返回适当的 5xx 和关联 ID，不得声称价格已刷新
