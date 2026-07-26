## ADDED Requirements

### Requirement: 只暴露具有有效 owner 的投递路径
本稳定版本 SHALL 以站内告警作为唯一可用通知事实，并 MUST NOT 显示或接受 Webhook 与浏览器系统通知启用操作，因为当前运行时没有负责重试投递或系统通知发送的完整 owner。创建止损告警 MUST NOT 创建无法被稳定消费的外部投递工作。

#### Scenario: 稳定模式触发告警
- **WHEN** legacy 持仓触发止损
- **THEN** 系统提交站内告警且不创建外部 DeliveryAttempt

#### Scenario: 直接请求通道配置
- **WHEN** 客户端直接尝试启用 Webhook 或浏览器系统通知能力
- **THEN** 系统返回稳定的 `feature_not_supported` 且不保存启用状态或密钥

## REMOVED Requirements

### Requirement: Keep in-app alerts independent from delivery
**Reason**: 外部投递工作不属于稳定运行时；站内告警独立性继续由告警 capability 约束。

**Migration**: 实现并调度外部投递 worker 后恢复该隔离要求。

### Requirement: Deliver idempotent signed webhooks safely
**Reason**: 当前没有运行时任务负责到期投递与重试。

**Migration**: 在单独且经过安全审查的 change 中同时重新引入 Webhook 配置与投递。

### Requirement: Request browser notification permission explicitly
**Reason**: 当前 UI 只请求权限，并未实际发送浏览器系统通知。

**Migration**: 保持控件隐藏；只有具备授权后的真实投递路径和浏览器测试时才重新引入。

### Requirement: Protect secrets and sensitive payloads
**Reason**: 稳定运行时不再接受 Webhook 密钥或 payload 配置。

**Migration**: 保留密钥存储实现供未来使用，并在恢复投递能力时重新加入该契约。
