## ADDED Requirements

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
