## MODIFIED Requirements

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
