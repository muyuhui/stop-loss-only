## ADDED Requirements

### Requirement: Configure extension settings safely
系统 SHALL 分组读取和更新历史保留、通知、导入限制和诊断设置，校验跨字段关系并只在持久化和运行时应用都成功后报告成功。

#### Scenario: Invalid retention value
- **WHEN** 用户提交超出支持范围的保留天数
- **THEN** 系统返回稳定字段错误且保留原运行时设置

### Requirement: Configure channels without exposing secrets
系统 SHALL 支持写入、替换、清除和禁用 Webhook 密钥，但读取设置 MUST NOT 返回完整密钥。

#### Scenario: Disable webhook
- **WHEN** 用户禁用 Webhook
- **THEN** 后续告警不创建新投递尝试，已有站内告警不变
