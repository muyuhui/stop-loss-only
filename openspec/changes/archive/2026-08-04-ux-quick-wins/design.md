## Context

当前稳定运行面（legacy / shadow-read）的 UX 短板集中在“最后一公里”：风险试算结果与新增持仓表单之间需要手工重录参数；手动平仓需要手输价格且无法预览结果；仪表盘已计算 `realized_profit_loss` 但前端未展示；告警页“全部标记已读”在无未读时仍可操作。四项均不需要后端 schema/API 变更或数据库迁移，属于纯前端改动（含少量前端工具函数与测试）。

约束：试算保持只读语义、稳定持仓写入只能走既有 `POST /api/holdings`、金额计算在前端仅作展示性估算（权威计算始终在后端 Decimal 引擎）、全部改动须通过 `.\verify.ps1`。

## Goals / Non-Goals

**Goals:**
- legacy/shadow-read 下，有效新仓试算结果可一键预填稳定持仓新增表单，消除手工重录往返。
- 手动平仓在可行动行情下预填平仓价，并在确认前展示预计毛已实现盈亏。
- 仪表盘资产摘要展示毛已实现盈亏，数据来自既有契约字段。
- 告警“全部标记已读”在无未读时禁用。

**Non-Goals:**
- 不改变任何后端 API、能力门禁、数据模型或迁移版本。
- 不引入自动建仓、自动平仓或任何绕过用户确认的写入。
- 不做 Position 域（new-authoritative）创建流程的改动。
- 不新增组合净值历史、通知管道升级等方向性功能。

## Decisions

### 1. 试算预填采用“路由参数 → 打开新增表单”而非直接提交

选择在 `RiskPlanner` 结果面板提供“填入新增持仓”入口，跳转 `/holdings?create=1&...` 并让 `Holdings.vue` 自动打开新增弹窗，`HoldingForm.vue` 接受初始值 props。

- 理由：复用既有表单校验、错误拦截、成功刷新与审计路径；保持“试算不写入”语义——planner 自身不调用任何写入 API；实现面最小。
- 备选 A：planner 内带确认弹窗直接调用 `POST /api/holdings`。否决：绕过稳定表单路径、重复实现校验与错误处理，且与“试算只读”语义冲突。
- 备选 B：Pinia store / sessionStorage 传递参数。否决：路由参数更直接、可测试，本地单用户场景无敏感信息泄露问题。

预填映射：`normalized_input.code/name/asset_type → code/name/type`；`entry_price → buy_price`（按资产精度取整：股票 2 位、基金 3 位，与 `priceInputMeta` 一致）；`recommended_quantity → quantity`（`Math.floor` 为整数）；`stop_method/stop_value → 止损方式/参数`；`buy_date` 默认取本地当天（Asia/Shanghai）。基金数量取整为整数份后，在表单中提示用户可调整。

### 2. 平仓预填与盈亏预览为纯前端展示计算

仅当 `holding.is_actionable === true` 且 `current_price != null` 时预填平仓价；确认弹窗中的预计毛已实现盈亏用 `(平仓价 - 买入价) × 数量` 计算，标注“不含费用、仅供参考”，最终以用户确认提交后的后端记录为准。

- 理由：与仪表盘 `realized_profit_loss` 的毛口径一致；不引入后端新端点；金额展示走既有 `formatMoney`。
- 备选：后端新增平仓预览端点。否决：为纯展示计算引入 API 不值得，且不改变权威口径。

### 3. 仪表盘新增“已实现盈亏”卡片

在 `metric-grid` 增加第四张卡片，数据直接使用 `dashboard.realized_profit_loss`，沿用 `valueTone` 语义着色；桌面端 `grid-template-columns` 从 3 列调整为 4 列，移动端保持两列。无已关闭持仓时显示 `0`（真实零，而非未知占位）。

### 4. 告警“全部标记已读”按全局未读数禁用

`Alerts.vue` 的按钮使用 `alertStore.unreadCount` 作为禁用依据，避免分页列表无法代表全局未读状态的问题。为避免计数加载失败（初始 0）造成按钮误禁用，给 `alert` store 增加 `countLoaded` 标记：仅在“已成功加载计数且为 0”时禁用；`markAll` 成功后同步刷新计数。

### 5. 将 DPAPI 桥接库声明为后端运行依赖

既有 `services/secret_store.py` 使用 Windows DPAPI 的 `win32crypt` 模块加密 DeepSeek Key，但当前依赖清单未包含其提供包，导致标准安装及 E2E 子进程在保存 Key 时返回 `409 machine_secret_storage_unavailable`。在 `backend/requirements.txt` 固定 `pywin32==312`，保持 DPAPI 加密和“密钥不入 SQLite、日志或备份”的既有安全边界；不引入明文回退或新的配置来源。

## Risks / Trade-offs

- [路由参数可被手工修改或过长] → 参数仅作预填建议，保存仍走后端完整校验；数量/价格非法时表单校验或后端 422 兜底，不产生副作用。
- [基金推荐数量向下取整后与试算风险金额不一致] → 表单明确提示“已按整数份取整，可调整”；正式创建后风险预算按实际持仓重算，试算不预留额度。
- [平仓预览为前端估算，可能与后端扣费后口径不同] → 文案标注“毛盈亏、不含费用、仅供参考”；权威事实仍是平仓提交后的记录。
- [告警计数加载失败导致按钮短暂禁用] → 引入 `countLoaded` 标记，仅成功加载后参与禁用判断；App 轮询会持续修正计数。
- [仪表盘卡片增多在窄屏挤压] → 移动端维持两列网格并复用现有 `metric-grid` 断点，不引入横向滚动。
- [`pywin32` 未随标准安装进入当前解释器] → 在后端固定依赖版本，并以同一解释器导入 `win32crypt` 和 DPAPI round-trip 测试验证；不采用明文回退。

## Migration Plan

无数据库迁移。纯前端改动，按变更任务分批提交；回滚即还原相关组件改动，不影响数据与 API。完成后运行 `.\verify.ps1` 全门禁（pytest 不受影响，前端 unit/mount 新增用例进入 `npm test`，E2E 覆盖新增入口不回归）。

## Open Questions

- 基金的最小买入单位是否一律为整数“份”？（当前 legacy `Holding.quantity` 为整数，假设成立；若未来支持小数份，需单独变更。）
- “填入新增持仓”入口在 `create=1` 参数缺失/非法时是否静默忽略？当前设计为忽略并保持正常列表行为。
