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
设置界面 SHALL 展示能够在当前稳定运行时实际应用并观察结果的页面轮询、价格监控、手动刷新、监控诊断和备份控制。风险政策输入 SHALL 仅在运行时声明风险预算读取或风险规划能力时展示。界面 MUST NOT 展示能力关闭的风险政策、未完成的 Webhook、浏览器系统通知、CSV 或数据留存配置，并 SHALL 使用一致中文文案说明配置值和实际生效状态。

#### Scenario: 打开 legacy 稳定设置页
- **WHEN** 用户打开设置页面且风险预算和规划能力均不可用
- **THEN** 页面从刷新频率开始展示受支持设置，不显示组合权益、组合风险上限、单笔风险上限、英文占位或不可完成的扩展操作

#### Scenario: 打开支持风险预算的设置页
- **WHEN** 受支持运行时声明风险预算读取或风险规划能力
- **THEN** 页面展示手工组合权益和风险上限，并明确其不是券商实时余额

#### Scenario: 保存监控间隔
- **WHEN** 用户在风险政策区域隐藏时保存有效页面轮询和价格监控间隔
- **THEN** 系统只提交并应用可见运行设置，已保存的风险政策值保持不变

### Requirement: Persist validated risk budget settings
The system SHALL read and update optional manual portfolio equity, portfolio risk limit percentage, and default per-position risk limit percentage through the runtime settings API using Decimal-safe representations. It MUST validate the three fields together, preserve prior effective values on failure, and return the equity last-update time.

#### Scenario: Read settings before equity is entered
- **WHEN** the settings store contains no portfolio equity
- **THEN** the response returns equity as unavailable, documented percentage defaults, and no fabricated update time

#### Scenario: Save complete risk settings
- **WHEN** the user submits valid equity and percentage limits with the other runtime settings
- **THEN** the system atomically persists the values and returns their Decimal-safe effective representations

#### Scenario: Reject invalid equity
- **WHEN** the user submits zero or negative portfolio equity
- **THEN** the system returns a stable field validation error and all previously effective runtime settings remain unchanged

#### Scenario: Preserve risk settings when updating monitoring
- **WHEN** the user changes only polling or monitoring intervals
- **THEN** the stored risk budget settings remain unchanged

### Requirement: 安全配置 DeepSeek 凭据
系统 SHALL 允许用户在设置页配置、替换和清除 DeepSeek API Key，并 MUST 使用现有 Windows 本机加密存储保存密钥。设置读取 SHALL 只返回是否已配置，不得返回密钥原文；密钥 MUST NOT 写入 SQLite、普通设置、日志、诊断包或备份。

#### Scenario: 首次保存 DeepSeek Key
- **WHEN** 用户提交符合长度限制的 DeepSeek API Key 且本机加密存储可用
- **THEN** 系统加密保存密钥，返回 `deepseek_api_key_configured=true`，且设置响应不包含密钥值

#### Scenario: 替换已有 Key
- **WHEN** 用户为已配置的 DeepSeek 提交新 Key
- **THEN** 系统原子替换本机密钥，后续请求只使用新值且永不回显旧值或新值

#### Scenario: 清除 DeepSeek Key
- **WHEN** 用户明确确认清除已配置 Key
- **THEN** 系统删除本机密钥并返回 `deepseek_api_key_configured=false`，后续复盘返回 `ai_not_configured`

#### Scenario: 本机密钥存储不可用
- **WHEN** 当前平台或依赖无法提供受支持的本机加密存储
- **THEN** 系统稳定拒绝保存，数据库和先前有效配置保持不变，且不得回退为明文文件或普通设置

### Requirement: 独立检测 DeepSeek 连接
设置界面 SHALL 提供用户主动触发的 DeepSeek 连接检测。检测 SHALL 使用当前已保存密钥向固定 DeepSeek Provider 发送不包含持仓数据的最小请求，并返回成功或稳定失败状态；检测失败 MUST NOT 清除或修改已保存凭据。

#### Scenario: 检测已配置连接
- **WHEN** 用户点击检测且 DeepSeek 返回有效最小响应
- **THEN** 页面显示连接成功和模型标识，不创建 AI 持仓复盘或业务记录

#### Scenario: 检测未配置连接
- **WHEN** 用户在没有 DeepSeek Key 时点击检测
- **THEN** 系统返回 `ai_not_configured`，不发送网络请求

#### Scenario: 检测失败
- **WHEN** DeepSeek 鉴权失败、超时、限流或不可用
- **THEN** 页面显示可理解的稳定错误和重试操作，已保存的配置状态保持不变且不展示供应商原始响应

### Requirement: 清晰展示第一版 AI 设置边界
设置页 SHALL 将 Provider 明确显示为 DeepSeek，说明 AI 复盘会把目标持仓的近期行情、止损和聚合风险事实发送到云端，并且第一版 MUST NOT 展示其他 Provider、自定义 Base URL、自动交易或后台定时复盘配置。

#### Scenario: 打开未配置的 AI 设置
- **WHEN** 运行时支持 AI 持仓复盘但尚未保存 DeepSeek Key
- **THEN** 设置页显示 DeepSeek 配置入口、数据发送说明和未配置状态

#### Scenario: 打开已配置的 AI 设置
- **WHEN** DeepSeek Key 已保存在本机
- **THEN** 设置页显示已配置状态、替换、清除和检测操作，但不显示任何可恢复密钥内容

### Requirement: 桌面通知设置持久化
系统 SHALL 在 `/api/settings` 提供并持久化三个桌面通知设置：`desktop_notifications_enabled`（布尔，默认 `false`，opt-in）、`desktop_notification_mode`（`full` / `redacted`，默认 `full`）、`desktop_notifications_paused`（布尔，默认 `false`）。`GET /api/settings` MUST 始终返回三键；`PUT /api/settings` MUST 接受三键并持久化（重启后保留）；非法 `desktop_notification_mode` 值 MUST 返回 422。

#### Scenario: 返回默认设置
- **WHEN** 用户请求 `GET /api/settings` 且从未修改桌面通知设置
- **THEN** `desktop_notifications_enabled` 为 `false`、`desktop_notification_mode` 为 `full`、`desktop_notifications_paused` 为 `false`

#### Scenario: 保存并回读设置
- **WHEN** 用户 `PUT /api/settings` 提交启用、`redacted` 模式与暂停状态
- **THEN** 三键持久化，`GET /api/settings` 回读一致

#### Scenario: 模式值非法
- **WHEN** 用户提交 `desktop_notification_mode` 为约定范围外的字符串
- **THEN** 系统返回 422，设置不变化

