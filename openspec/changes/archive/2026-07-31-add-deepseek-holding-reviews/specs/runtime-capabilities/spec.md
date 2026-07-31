## ADDED Requirements

### Requirement: 独立声明 AI 持仓复盘能力
运行时能力契约 SHALL 增加稳定布尔字段 `ai_holding_reviews`，其值只表示当前权威阶段和稳定运行面是否实现该能力，不包含 DeepSeek Key 是否已配置、Provider 错误、持仓事实或其他敏感信息。AI 路由守卫和前端入口 MUST 使用同一服务端能力策略。

#### Scenario: legacy 稳定运行面
- **WHEN** 当前权威阶段为受支持的 `legacy`
- **THEN** 能力响应声明 `ai_holding_reviews=true`，前端可以展示复盘入口或配置引导

#### Scenario: shadow-read 稳定运行面
- **WHEN** 当前权威阶段为受支持的 `shadow-read`
- **THEN** 能力响应继续声明 `ai_holding_reviews=true`，复盘只读取 legacy Holding 权威事实

#### Scenario: 不受支持的新权威运行面
- **WHEN** 当前权威阶段为 `new-authoritative`
- **THEN** 能力响应声明 `ai_holding_reviews=false`，前端隐藏复盘命令且直接 API 请求稳定拒绝

#### Scenario: 能力可用但 Key 未配置
- **WHEN** `ai_holding_reviews=true` 但本机没有 DeepSeek Key
- **THEN** 能力响应仍保持结构性能力为 true，设置响应单独报告未配置，持仓详情入口引导用户配置而不泄露任何密钥状态到公开能力元数据之外
