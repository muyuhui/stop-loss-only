## ADDED Requirements

### Requirement: 待处置持仓队列
仪表盘 SHALL 在存在 `triggered` 持仓时展示"待处置持仓"队列：列出每笔已触发持仓（名称/代码、当前价与止损价、状态标签）并提供"去处置"直达对应详情页的入口；没有已触发持仓时 MUST 不渲染该区域。队列数据 MUST 与仪表盘既有载荷同源（`triggered_count` 与持仓列表），MUST NOT 发起额外请求。

#### Scenario: 存在已触发持仓
- **WHEN** 组合中存在 `triggered` 持仓
- **THEN** 仪表盘在风险区后展示待处置队列，每项可直达 `/holdings/:id` 处置页

#### Scenario: 没有已触发持仓
- **WHEN** 组合中不存在 `triggered` 持仓
- **THEN** 仪表盘不渲染待处置区域，其余内容不受影响
