# notification-delivery Specification

## Purpose
TBD - created by archiving change extend-local-platform. Update Purpose after archive.
## Requirements
### Requirement: Keep in-app alerts independent from delivery
系统 SHALL 在主事务中提交站内告警事实，只在提交成功后创建外部投递尝试；任何通道失败 MUST NOT 回滚仓位、事件或站内告警。

#### Scenario: Webhook is unavailable
- **WHEN** 已提交告警的 Webhook 目标超时
- **THEN** 投递尝试记录失败和下次重试时间，告警与仓位保持已提交

#### Scenario: Trigger transaction rolls back
- **WHEN** 触发主事务回滚
- **THEN** 系统不得创建对应外部投递尝试

### Requirement: Deliver idempotent signed webhooks safely
系统 SHALL 仅向通过 SSRF 校验的 HTTPS 目标发送带稳定幂等键、时间戳和 HMAC 签名的最小 payload，并实施硬超时和有限重试。

#### Scenario: Unsafe destination
- **WHEN** 目标解析到环回、私网或链接本地地址且未启用开发覆盖
- **THEN** 系统拒绝保存或投递并返回稳定安全错误

### Requirement: Request browser notification permission explicitly
前端 SHALL 只在用户明确操作后请求系统通知权限，并在拒绝或不支持时继续提供完整站内告警。

#### Scenario: Permission is denied
- **WHEN** 用户拒绝浏览器通知权限
- **THEN** 页面显示降级状态且不得重复自动弹出权限请求

### Requirement: Protect secrets and sensitive payloads
系统 SHALL 使用 Windows 本机保护存储保存 Webhook 密钥，不得在 API、日志或诊断包回显完整密钥；默认 payload 不包含数量、成本或总资产。

#### Scenario: Read notification settings
- **WHEN** 已保存密钥后读取设置
- **THEN** API 只返回已配置标志和非敏感元数据

