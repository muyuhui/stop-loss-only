## MODIFIED Requirements

### Requirement: Group settings by operational responsibility
设置界面 SHALL 只展示能够在本稳定运行时实际应用并观察结果的页面轮询、价格监控、手动刷新、监控诊断和备份控制。界面 MUST NOT 展示未完成的 Webhook、浏览器系统通知、CSV 或 retention 配置，并 SHALL 使用一致中文文案说明配置值和实际生效状态。

#### Scenario: 打开稳定设置页
- **WHEN** 用户打开设置页面
- **THEN** 页面只显示受支持且有完整后端行为的设置组，不出现英文占位或不可完成的扩展操作

#### Scenario: 保存监控间隔
- **WHEN** 用户保存有效页面轮询和价格监控间隔
- **THEN** 系统同时持久化并应用设置，页面显示实际生效值

## REMOVED Requirements

### Requirement: Configure extension settings safely
**Reason**: 保留策略、导入、通知和诊断扩展组并非全部具有实际运行时行为。

**Migration**: 只保留受支持的监控设置；每个扩展组必须连同负责它的 worker 和验收测试一起恢复。

### Requirement: Configure channels without exposing secrets
**Reason**: 在投递具有有效 owner 前，从稳定运行面移除 Webhook 通道配置。

**Migration**: 保留已存密钥，但在恢复通知投递 change 前不得暴露或修改通道配置。
