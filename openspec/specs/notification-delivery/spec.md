# notification-delivery Specification

## Purpose
定义稳定通知事实与外部投递隔离边界；当前站内告警可用，缺少完整运行时 owner 的 Webhook 与浏览器系统通知默认拒绝。
## Requirements
### Requirement: 只暴露具有有效 owner 的投递路径
本稳定版本 SHALL 以站内告警作为唯一可用通知事实，并 MUST NOT 显示或接受 Webhook 与浏览器系统通知启用操作，因为当前运行时没有负责重试投递或系统通知发送的完整 owner。创建止损告警 MUST NOT 创建无法被稳定消费的外部投递工作。

#### Scenario: 稳定模式触发告警
- **WHEN** legacy 持仓触发止损
- **THEN** 系统提交站内告警且不创建外部 DeliveryAttempt

#### Scenario: 直接请求通道配置
- **WHEN** 客户端直接尝试启用 Webhook 或浏览器系统通知能力
- **THEN** 系统返回稳定的 `feature_not_supported` 且不保存启用状态或密钥

