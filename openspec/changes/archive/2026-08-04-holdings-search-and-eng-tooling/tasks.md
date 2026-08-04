# Tasks — Holdings 搜索筛选与工程工具链优化

## 1. 后端列表查询参数

- [x] 1.1 `backend/routers/holdings.py::list_holdings` 新增 `search` 参数：对 `Holding.name`/`Holding.code` 做转义后的包含匹配（复用 alerts.py 的 `contains(autoescape=True)` 模式，含 `ESCAPE` 子句）；空白值视为未提供
  **验收**：`GET /api/holdings?search=银行` 只返回名称/代码含子串的持仓；`%`/`_` 按字面量匹配
- [x] 1.2 新增 `type` 参数（`pattern="^(stock|fund)$"`）等值过滤，非法值 422
  **验收**：`type=stock`/`type=fund` 分别只返回对应类型；`type=xxx` 返回 422
- [x] 1.3 新增 `sort` 参数（`pattern="^(newest|name|risk)$"`）：`newest` 保持现状排序；`name` 按 `name ASC, id ASC`；`risk` 用 `CASE WHEN current_price > 0 THEN (current_price - stop_loss_price) / current_price END` 升序 + `NULLS LAST` + `id ASC` 平局键；非法值 422
  **验收**：三种排序稳定分页；`risk` 下无估值持仓排最后、距离最小（含已触发负距离）排最前
- [x] 1.4 保证组合语义：过滤（status/type/search）→ 排序 → `total`（过滤后）→ 切片；无参数时行为与现状逐字节一致
  **验收**：`test_api.py` 现有列表契约测试全部通过且无需修改

## 2. 后端契约测试

- [x] 2.1 在 `backend/tests/` 新增列表查询契约测试（沿用既有内存库 bootstrap 模式：StaticPool + `dependency_overrides[get_db]` + TestClient）
  **验收**：覆盖 search 命中/未命中/空值、`%`/`_` 转义、search+status+type 组合、sort=newest/name/risk 顺序（unpriced 排最后、负距离排最前）、非法 sort/type → 422、筛选后 total 与分页切片正确
- [x] 2.2 `risk` 排序与展示口径一致性测试：断言 SQL 排序结果的首尾顺序与 `holding_payload` 计算的 `stop_loss_distance_pct` 一致
  **验收**：测试通过；如发现列漂移，按 design D2 兜底方案在实现中切换为 Python 全量排序并更新本任务说明

## 3. 前端工具栏

- [x] 3.1 将 `frontend/src/components/FilterToolbar.vue` 重命名为 `HoldingsToolbar.vue` 并重写选项语义为 legacy Holding：搜索输入（名称或代码）、状态（全部/持有中/已触发/已关闭）、类型（全部/A股/基金）、排序（最新优先/名称/风险优先）、重置、总数；保留 `query`/`update:query`/`reset` 事件形态与 ≤767px 双列响应式
  **验收**：无 position-only 选项；移动端无横向滚动
- [x] 3.2 `Holdings.vue` 接入工具栏：按 Alerts.vue 模式持有 `query` ref、任一变化重置 `page: 1`、空搜索词不发 `search` 参数、保持 DataState/加载/错误/空状态与分页行为
  **验收**：搜索/筛选/排序触发带 `page: 1` 的新请求；列表交互与详情入口正常
- [x] 3.3 前端 mount 测试（`vi.mock('../src/api')`）：输入搜索词触发带 `page: 1` 的查询、切换下拉触发刷新、重置恢复默认并回第 1 页、移动端布局类名存在
  **验收**：`npm test` 中新增 spec 通过

## 4. 排序偏好记忆

- [x] 4.1 排序选择写入 localStorage（键 `holdings.sort`），进入页面时读取并校验枚举，非法/缺失回退 `newest`；搜索词与筛选不持久化
  **验收**：选择"风险优先"后重进页面恢复；localStorage 写入脏值时代码回退默认
- [x] 4.2 记忆逻辑测试：`node:test` 纯逻辑测试（读取/校验/回退）与 mount 测试（选择→写入、恢复→应用）
  **验收**：`npm test` 通过

## 5. E2E 场景

- [x] 5.1 在 `frontend/tests/e2e/supported-runtime.spec.js` 增加场景：seed 3 笔不同名称/类型/价格的持仓（`page.request.post('/api/holdings')` + fixture 价格），断言：搜索收窄列表与总数、`risk` 排序首项为最近止损持仓、mobile-390 视口下工具栏可用且 `assertPageIntegrity` 通过
  **验收**：`npm run test:e2e` 全场景（含既有 7 个）通过

## 6. README 与工具链

- [x] 6.1 删除 README「v4 回滚」节，替换为当前版本回滚 runbook：`stop.ps1` → `backup.ps1` → `python db_admin.py status`（确认当前版本，文案以命令输出为准而非硬编码版本号）→ `python db_admin.py downgrade`（说明非破坏性：新列/索引/表保留）→ 重启；数据恢复仍指向 `restore.ps1`
  **验收**：README 不再出现 v4 专属回滚步骤；文档与 `LATEST_SCHEMA_VERSION=8` 现状一致
- [x] 6.2 README「安装」节补充环境要求：Python ≥ 3.12、Node ≥ 20.19、npm ≥ 7、openspec CLI（仅验证门禁需要）
  **验收**：文档可读且与 setup.ps1 预检口径一致
- [x] 6.3 新增根目录 `.python-version`（内容 `3.12`）
  **验收**：文件存在，内容为 `3.12`
- [x] 6.4 `setup.ps1` 开头新增 Python 版本预检（解析 `python --version`，major.minor ≥ 3.12，解析失败按不满足处理）与 openspec CLI 预检（`Get-Command openspec`）；缺失时中文错误信息 + 安装指引并以非零码退出
  **验收**：低于 3.12 或缺少 openspec 时 setup 明确报错退出；正常环境安装流程不变

## 7. 门禁与同步

- [x] 7.1 运行 `.\verify.ps1` 全量门禁（pytest、npm test、build+包体预算、E2E、smoke、restore drill、openspec validate）并修复所有回归
  **验收**：门禁全部通过
- [x] 7.2 `/opsx:sync` 将 delta spec 同步进主 specs，更新 CLAUDE.md（如需反映命令/环境要求变化）后 `/opsx:archive`
  **验收**：主 spec `openspec/specs/holdings-crud/spec.md` 含新需求；change 归档
