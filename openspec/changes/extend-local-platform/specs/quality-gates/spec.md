## ADDED Requirements

### Requirement: Test extension isolation and security
测试套件 SHALL 验证投递失败不回滚核心事实、重复任务幂等、SSRF 目标被拒绝、密钥不出现在响应或日志，以及系统通知权限降级。

#### Scenario: Delivery fails after trigger
- **WHEN** Webhook 超时或返回失败
- **THEN** 测试证明触发、事件和站内告警仍已提交且没有敏感日志

### Requirement: Test import export and recovery boundaries
测试套件 SHALL 覆盖非法/超大 CSV、过期预览、公式注入、Decimal 往返、同秒多次备份、不兼容 manifest、损坏数据库和 readiness 自动恢复。

#### Scenario: Import commit partially fails
- **WHEN** 一个已预览批次在提交时违反领域约束
- **THEN** 整个导入事务回滚且返回稳定逐行错误
