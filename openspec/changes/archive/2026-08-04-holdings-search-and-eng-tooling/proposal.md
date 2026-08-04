# Holdings 搜索筛选与工程工具链优化

## Why

持仓页在持仓数量增多后只能翻页查找，缺少搜索、状态筛选和按风险排序——而仓库里已有一个为废弃 Position 世界编写的孤儿 `FilterToolbar.vue` 从未接线。与此同时，README 的"v4 回滚"runbook 已过期（schema 已到 v8）、Python 版本无任何锁定、`setup.ps1` 不安装 openspec CLI 导致新环境 `verify.ps1` 必然最后一步失败。这些是低风险、高确定性的改进，先于新功能落地。

## What Changes

- `GET /api/holdings` 新增 `search` 查询参数：按名称或代码做转义后的包含匹配，与现有 `status` 筛选及新增 `type` 筛选可组合，默认行为不变。
- `GET /api/holdings` 新增 `type` 查询参数（`stock` / `fund`）按资产类型筛选；`sort` 查询参数（`newest` 默认 / `name` / `risk`）：`risk` 按止损距离升序、无估值行情持仓排最后、稳定平局排序；非法值返回 422。
- 筛选与排序在分页之前应用，`total` 始终反映过滤后的记录数。
- 前端持仓页新增工具栏（搜索输入、状态筛选、类型筛选、排序选择、总数展示），复用并改造孤儿 `FilterToolbar.vue` 为 legacy Holding 语义；筛选变化重置到第 1 页；≤767px 双列响应式。
- 排序选择通过 localStorage 记忆并在下次进入页面时恢复；搜索词与筛选不持久化。
- README「v4 回滚」段落更新为当前 schema 版本（v8）的回滚 runbook，并补充环境要求（Python 版本）。
- 新增 `.python-version`（3.12）并在 `setup.ps1` 增加 Python 版本预检（低于要求时以明确中文错误退出）。
- `setup.ps1` 增加 openspec CLI 预检：缺失时给出明确中文安装指引并退出，避免 `verify.ps1` 到最后一步才失败。
- 配套测试：后端契约测试（搜索转义、排序语义、组合筛选）、前端 mount 测试（工具栏交互、排序记忆）、E2E 场景（搜索收窄列表、风险排序、响应式）。

## Capabilities

### New Capabilities

（无——本 change 不引入新的运行面能力）

### Modified Capabilities

- `holdings-crud`: 列表查询契约新增搜索与排序参数；前端持仓页新增搜索/筛选/排序工具栏与排序偏好记忆

## Impact

- API: `backend/routers/holdings.py`（`list_holdings` 查询参数与查询构造）
- 前端: `frontend/src/views/Holdings.vue`、`frontend/src/components/FilterToolbar.vue`（改造复用）、`frontend/src/utils/`（排序/偏好小工具）
- 工具链: `setup.ps1`、新增 `.python-version`、`README.md`（回滚 runbook 与环境要求）
- 测试: `backend/tests/test_api.py`（或新增模块）、`frontend/tests/*.mount.spec.js`、`frontend/tests/*.test.js`、`frontend/tests/e2e/`
- 无数据库 schema 变更、无迁移。
