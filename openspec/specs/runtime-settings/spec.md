# Runtime Settings

## Purpose

统一管理前端页面轮询间隔与后端行情监控间隔，确保所有配置都经过服务端范围校验、可靠持久化，并能在运行期间动态应用以及在服务重启后自动恢复，避免数据库配置与实际运行状态不一致。
## Requirements
### Requirement: 获取运行时设置
系统 SHALL 返回生效中的前端轮询间隔和后端监控间隔；未保存时使用文档约定的默认值。

#### Scenario: 尚未保存设置
- **WHEN** 设置表为空且用户请求 `GET /api/settings`
- **THEN** 响应包含默认轮询和监控间隔

#### Scenario: 已保存设置
- **WHEN** 用户保存过有效设置后再次查询
- **THEN** 响应包含当前生效的持久化值

### Requirement: 校验并应用运行时设置
系统 SHALL 将轮询间隔限制为 5–300 秒、监控间隔限制为 1–60 分钟；只有运行时应用成功后才持久化完整变更。

#### Scenario: 提交有效设置
- **WHEN** 用户提交范围内的间隔
- **THEN** 系统应用并保存设置，返回生效值

#### Scenario: 提交非法设置
- **WHEN** 任一间隔超出范围
- **THEN** 系统返回 422，持久化值和运行状态均不变化

#### Scenario: 运行时应用失败
- **WHEN** 调度器无法应用已通过校验的新间隔
- **THEN** 系统返回错误，数据库和调度器均保持旧值

### Requirement: 启动时恢复设置
系统 SHALL 在启动调度器之前读取有效的持久化监控间隔。

#### Scenario: 修改设置后重启服务
- **WHEN** 后端启动时数据库中存在有效监控间隔
- **THEN** 调度器使用该值，而不是硬编码值

### Requirement: 前端使用轮询设置
前端 SHALL 使用生效轮询间隔控制仪表盘和告警轮询，并在设置变化时替换计时器。

#### Scenario: 加载轮询设置
- **WHEN** 前端读取到 45 秒轮询间隔
- **THEN** 相关轮询按 45 秒执行

#### Scenario: 修改轮询设置
- **WHEN** 用户保存新的有效轮询间隔
- **THEN** 活动轮询切换到新间隔，且不会出现重复计时器

### Requirement: 易理解的运行时设置界面
前端 SHALL 默认使用易理解的刷新预设表达页面轮询和价格监控频率，同时通过高级设置保留现有有效范围内的精确控制。

#### Scenario: 使用均衡预设
- **WHEN** 用户选择“均衡”并保存
- **THEN** 前端提交页面轮询 30 秒和价格监控 5 分钟，并在成功后继续显示“均衡”为当前预设

#### Scenario: 使用及时预设
- **WHEN** 用户选择“及时”并保存
- **THEN** 前端提交页面轮询 10 秒和价格监控 1 分钟

#### Scenario: 使用省资源预设
- **WHEN** 用户选择“省资源”并保存
- **THEN** 前端提交页面轮询 60 秒和价格监控 15 分钟

#### Scenario: 当前设置不匹配预设
- **WHEN** 服务端返回的两个间隔不匹配任何内置预设
- **THEN** 页面显示“自定义”，并在高级设置中展示实际生效数值

#### Scenario: 手机端编辑高级设置
- **WHEN** 用户在 360px 到 767px 宽的视口展开高级设置
- **THEN** 两个间隔字段、说明和保存操作按单列完整显示且不产生横向滚动

#### Scenario: 保存设置失败
- **WHEN** 设置请求失败或服务端拒绝应用
- **THEN** 页面保留先前生效值，显示可理解的失败信息并允许重新提交

### Requirement: Group settings by operational responsibility
设置界面 SHALL 将监控、行情与历史、通知占位以及数据与诊断按责任分组，并展示配置值、实际生效值和调度器状态。

#### Scenario: Preset is applied
- **WHEN** 用户选择及时、均衡或省资源预设
- **THEN** 页面展示将要改变的实际字段并在保存成功后显示生效状态

#### Scenario: Save fails
- **WHEN** 后端拒绝或无法应用设置
- **THEN** 页面保留用户输入、显示可定位错误且不声称已生效

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

