## ADDED Requirements

### Requirement: Group settings by operational responsibility
设置界面 SHALL 将监控、行情与历史、通知占位以及数据与诊断按责任分组，并展示配置值、实际生效值和调度器状态。

#### Scenario: Preset is applied
- **WHEN** 用户选择及时、均衡或省资源预设
- **THEN** 页面展示将要改变的实际字段并在保存成功后显示生效状态

#### Scenario: Save fails
- **WHEN** 后端拒绝或无法应用设置
- **THEN** 页面保留用户输入、显示可定位错误且不声称已生效
