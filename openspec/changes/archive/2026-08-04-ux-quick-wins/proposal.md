## Why

当前稳定 legacy/shadow-read 运行面存在几处“最后一公里”断层：风险试算与新增持仓之间需要手工重录全部参数；手动平仓要手输平仓价且无法预览将实现的盈亏；仪表盘后端已返回 `realized_profit_loss` 但前端从不展示；告警“全部标记已读”在无未读时仍可点击。这些都不需要后端新能力或数据迁移，属于低成本、高感知的 UX 补齐。

## What Changes

- 风险试算（新仓）：legacy/shadow-read 下，有效新仓结果新增“填入新增持仓”入口，将规范化输入与推荐数量预填到稳定持仓新增表单；入口不自动提交、不绕过校验、不调用写入 API。new-authoritative 的受约束 Position 创建流程保持不变。
- 持仓详情手动平仓：持仓具有可行动当前行情时预填平仓价；确认弹窗展示按输入计算的预计已实现盈亏（`(平仓价 - 买入价) × 数量`）。
- 仪表盘：资产摘要新增“已实现盈亏”展示，数据来自既有 `realized_profit_loss` 契约字段，不改变 API。
- 告警页：无未读告警时禁用“全部标记已读”按钮（对齐并补全 `alert-system` 既有“禁用或隐藏无意义操作”要求，纯实现修复）。
- Windows 本机密钥存储：补齐 `pywin32` 运行依赖，使既有 DPAPI 密钥存储可在标准安装和 E2E 环境中导入 `win32crypt`；不改变密钥存储策略、API 或数据模型。
- 无后端 API 变更、无数据库迁移、无运行时能力变更。

## Capabilities

### New Capabilities

<!-- 无新增能力 -->

### Modified Capabilities

- `position-sizing-planner`: 调整“试算结果交接到建仓”的稳定运行面语义——legacy/shadow-read 允许把有效新仓试算结果预填到稳定持仓新增表单，但仍保持试算只读、不自动写入；新增预填与 legacy 整数数量取整场景。
- `holdings-crud`: 手动平仓交互新增“可行动行情预填平仓价”与“确认时展示预计已实现盈亏”场景。
- `dashboard`: 仪表盘资产摘要新增“已实现盈亏”展示场景（契约字段已存在）。

## Impact

- 前端：`RiskPlanner.vue`（结果入口与预填参数组装）、`Holdings.vue` / `HoldingForm.vue`（按入口参数打开新增表单并预填）、`HoldingDetail.vue`（平仓预填与确认预览）、`Dashboard.vue`（已实现盈亏卡片）、`Alerts.vue`（全部已读按钮禁用）。
- 后端：新增固定的 Windows 运行依赖 `pywin32==312`，无 schema/API 变更；复用 `POST /api/holdings`、`GET /api/dashboard`、`GET /api/alerts/count`。
- 数据与兼容：legacy `Holding.quantity` 为整数，基金试算推荐数量可能为小数，预填时向下取整为整数份并在表单中提示可调整。
- 测试：前端 unit/mount 测试覆盖预填、平仓预览、仪表盘卡片与按钮禁用；后端测试不受影响；最终通过 `.\verify.ps1` 全门禁。
