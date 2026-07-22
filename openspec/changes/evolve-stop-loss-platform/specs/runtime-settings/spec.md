## ADDED Requirements

### Requirement: Group extended runtime settings by responsibility
系统 SHALL 把设置分为 monitoring、quotes、history、notifications 和 data 分组，并为每个字段提供服务端默认值、范围校验、敏感性和是否需要运行时应用的元数据。

#### Scenario: Read all settings
- **WHEN** 用户请求设置摘要
- **THEN** 响应返回各分组生效值和可公开元数据，但不返回通知密钥明文

#### Scenario: Update one group
- **WHEN** 用户只更新 history 保留时间
- **THEN** 其他分组保持不变，响应返回完整生效 history 分组

### Requirement: Configure quote and history policies safely
系统 SHALL 校验各资产新鲜度、历史保留时间和诊断保留时间，并在保存前验证跨字段关系。

#### Scenario: Valid history retention
- **WHEN** 用户把行情历史保留时间设为允许范围内的 730 天
- **THEN** 设置持久化且后续清理周期使用新值

#### Scenario: Invalid freshness relationship
- **WHEN** 延迟行情允许年龄超过系统允许上限或小于零
- **THEN** 系统返回 422 且旧策略继续生效

### Requirement: Configure notification channels without exposing secrets
系统 SHALL 支持启用、禁用和测试通知通道，敏感字段只允许替换和清除，不允许通过读取接口完整返回。

#### Scenario: Replace webhook secret
- **WHEN** 用户提交新密钥
- **THEN** 系统安全保存新值，响应只返回 `secret_configured=true`

#### Scenario: Disable channel
- **WHEN** 用户禁用 Webhook
- **THEN** 后续告警不创建该通道投递任务，既有告警事实不变化

## MODIFIED Requirements

### Requirement: 校验并应用运行时设置
系统 SHALL 对每个设置分组执行强类型范围和跨字段校验；需要影响运行中组件的变更只有在应用成功后才持久化完整分组，其他分组不得受失败影响。

#### Scenario: 提交有效监控设置
- **WHEN** 用户提交范围内的页面轮询和后端监控间隔
- **THEN** 系统应用并保存 monitoring 分组，返回实际生效值

#### Scenario: 提交非法历史或行情设置
- **WHEN** 任一字段超出范围或违反跨字段约束
- **THEN** 系统返回 422，相关分组的持久化值和运行状态均不变化

#### Scenario: 调度器运行时应用失败
- **WHEN** 调度器无法应用已通过校验的新间隔
- **THEN** 系统返回稳定错误，数据库和调度器均保持旧值

#### Scenario: 通知测试失败
- **WHEN** 用户测试一个已通过格式校验但不可达的通知通道
- **THEN** 系统返回测试失败诊断，但不影响监控和站内告警设置

### Requirement: 易理解的运行时设置界面
前端 SHALL 默认使用易理解的刷新预设，并按“刷新与监控、行情与历史、通知、数据与诊断”分组渐进展示高级设置、实际生效值、运行状态和失败恢复操作。

#### Scenario: 使用均衡预设
- **WHEN** 用户选择“均衡”并保存
- **THEN** 前端提交页面轮询 30 秒和价格监控 5 分钟，并继续显示“均衡”为生效预设

#### Scenario: 当前设置不匹配预设
- **WHEN** 服务端返回的两个间隔不匹配内置预设
- **THEN** 页面显示“自定义”并展示实际生效数值

#### Scenario: 手机端编辑高级设置
- **WHEN** 用户在 360px 到 767px 视口展开任一高级设置组
- **THEN** 字段、说明、状态和保存操作按单列完整显示且不产生横向滚动

#### Scenario: 保存设置失败
- **WHEN** 设置请求失败或服务端拒绝运行时应用
- **THEN** 页面保留先前生效值，指出失败分组并允许重新提交
