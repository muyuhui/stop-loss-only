## ADDED Requirements

### Requirement: Keep in-app alerts independent from delivery
系统 SHALL 在止损主事务中提交站内告警事实，并只在提交成功后创建外部投递任务；任何外部通道失败不得回滚仓位、事件或站内告警。

#### Scenario: Webhook is unavailable
- **WHEN** 止损已触发但 Webhook 目标超时
- **THEN** 仓位和站内告警保持已提交，投递记录标记失败并按策略重试

#### Scenario: Trigger transaction rolls back
- **WHEN** 止损触发事务未成功提交
- **THEN** 系统不得创建或发送对应外部通知

### Requirement: Deliver idempotent signed webhooks
系统 SHALL 为启用的 HTTPS Webhook 使用稳定幂等键、时间戳和可验证签名发送最小 payload，并应用超时、有限重试和 SSRF 防护。

#### Scenario: Receiver returns success
- **WHEN** Webhook 接收端在超时内返回 2xx
- **THEN** 投递记录变为 `delivered` 且不会因调度重试重复发送

#### Scenario: Duplicate delivery job
- **WHEN** 同一告警和通道的任务被重复调度
- **THEN** 幂等约束只允许一个有效投递序列

#### Scenario: Unsafe destination
- **WHEN** 用户配置被策略禁止的环回、私网或链接本地地址
- **THEN** 系统拒绝保存并返回可理解的校验错误

### Requirement: Request browser notification permission explicitly
前端 SHALL 只在用户明确操作后请求系统通知权限，并在权限拒绝或浏览器不支持时继续提供完整站内告警。

#### Scenario: User enables system notifications
- **WHEN** 用户在设置页点击启用且浏览器返回授权
- **THEN** 前端保存启用状态并对后续新告警显示系统通知

#### Scenario: Permission is denied
- **WHEN** 浏览器拒绝通知权限
- **THEN** 页面显示非阻塞说明，站内告警和未读计数继续工作

### Requirement: Protect notification secrets and sensitive payloads
系统 SHALL 默认发送不含数量、成本和总资产的基础通知，密钥不可完整回显，只有用户明确选择详情级别时才允许发送额外持仓字段。

#### Scenario: Read notification settings
- **WHEN** 已保存 Webhook 密钥后用户重新打开设置
- **THEN** 响应只返回已配置标志或掩码，不返回完整密钥

#### Scenario: Basic privacy level
- **WHEN** 通道使用默认基础信息级别
- **THEN** payload 只包含告警 ID、标的标识、触发状态和时间，不包含数量、成本或组合金额
