## MODIFIED Requirements

### Requirement: Scheduled price monitoring
系统 SHALL 按运行时设置的间隔只对 legacy 权威模型中的活动持仓执行价格监控，只将状态为 `live`、`delayed` 或符合资产策略的 `nav` 行情用于更新和止损判断，并记录周期结果。Shadow position 数据 MUST NOT 成为第二写源或重复触发来源。

#### Scenario: Shadow Position 映射活动持仓
- **WHEN** 调度周期运行且数据库存在对应 shadow position
- **THEN** 系统只更新和触发一次 legacy holding，并在提交后按现有 shadow 规则投影

### Requirement: Manual price refresh API
系统 SHALL 提供全量和按标的或持仓限定范围的手动刷新 API，返回周期 ID、成功/失败计数、稳定错误详情和仅包含已提交触发的结果。两个入口 MUST 使用相同的错误映射，并保留预期业务 HTTP 状态。

#### Scenario: 已有刷新正在运行
- **WHEN** 全量或限定范围刷新无法在有界等待内取得刷新锁
- **THEN** API 返回 HTTP 409、`refresh_busy`、周期 ID，且不得被转换为 HTTP 500

#### Scenario: 数据库忙
- **WHEN** 全量或限定范围刷新无法在有界时间内建立数据库周期
- **THEN** API 返回 HTTP 503、`database_busy` 和周期 ID

#### Scenario: 未知刷新故障
- **WHEN** 刷新发生未分类内部异常
- **THEN** API 返回 HTTP 500、稳定错误码和关联 ID，不泄露行情响应或持仓数据
