## ADDED Requirements

### Requirement: 展示交易时段与行情时效
仪表盘 SHALL 呈现交易时段徽标（`pre_market`/`open`/`lunch`/`closed` 映射为 盘前/交易中/午休/已收盘，来源为 `/api/monitoring/status` 的 `market_session`）与持仓行情时效（口径与持仓列表一致）；时段指示 MUST 只表达时间语义，不判定节假日，且 MUST NOT 影响任何监控或触发行为。行情不可用时 MUST 不显示时效或年龄。

#### Scenario: 盘中展示交易中
- **WHEN** `/api/monitoring/status` 返回 `market_session` 为 `open`
- **THEN** 仪表盘显示"交易中"徽标，且与覆盖率、监控状态同区域展示

#### Scenario: 午休或收盘展示对应徽标
- **WHEN** `/api/monitoring/status` 返回 `lunch` 或 `closed`
- **THEN** 仪表盘显示"午休"或"已收盘"徽标

#### Scenario: 行情时效随持仓展示
- **WHEN** 持仓概览包含拥有可估值行情的活动持仓
- **THEN** 对应卡片显示与持仓列表同一口径的时效文本；未定价持仓不显示时效

#### Scenario: 状态不可用时降级
- **WHEN** `/api/monitoring/status` 请求失败或 `market_session` 缺失
- **THEN** 仪表盘不显示时段徽标且不出现错误，其余监控信息正常呈现
