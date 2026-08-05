# Tasks — 本月账本：仪表盘月度盈亏与纪律统计

## 1. 后端月度聚合

- [x] 1.1 `backend/routers/dashboard.py::get_dashboard` 增加月界计算：Asia/Shanghai 本月 1 日 00:00 与下月 1 日 00:00 → naive UTC（复用今日告警的转换模式）；`month` 标签 `YYYY-MM`
  **验收**：月界与今日告警同口径；标签为上海时区当前月
- [x] 1.2 计算 `realized_profit_loss` 与 `closed_count`：`status == "closed"`、`close_price` 非空、`updated_at` 落在月界内（Decimal 计算，注释说明 updated_at 平仓后冻结即平仓时间）
  **验收**：本月/上月平仓分别正确归属
- [x] 1.3 计算 `triggered_count`（本月 `Alert.created_at`）与 `stop_adjustment_count` / `stop_lowered_count`（`stop_rule_history` 月界内 `source in (update, rearm)`；调低 = 同一持仓按 `(changed_at, id)` 排序后当前 `stop_loss_price <` 上一条历史，create 为基线、无上一条不计入）
  **验收**：调高/调低/rearm/月内首条 create 各边界方向统计正确
- [x] 1.4 计算 `largest_loss`：可估值当前持仓中 `(current_price − buy_price) × quantity` 最小且为负者 → `{name, code, profit_loss_amount}`，否则 null
  **验收**：全部浮盈或无可估值持仓时返回 null
- [x] 1.5 `backend/schemas.py` 新增 `LargestLoss` 与 `MonthSummary`（金额 float，沿用 dashboard 口径），`DashboardResponse` 增加必填 `month_summary`
  **验收**：`/api/dashboard` 序列化含新字段，旧字段不变

## 2. 后端契约测试

- [x] 2.1 新增 `backend/tests/test_month_ledger.py`（沿用内存库 bootstrap：StaticPool + `dependency_overrides[get_db]` + TestClient），以 session 直接造数控制时间戳
  **验收**：覆盖本月/上月 closed 归属、本月/上月告警计数、调整方向统计（调低/调高/rearm/无基线）、空组合零值、全部浮盈时 `largest_loss` null、`month` 标签格式
- [x] 2.2 既有 `test_api.py` 的 dashboard 契约测试回归通过（`month_summary` 不影响旧断言）
  **验收**：`python -m pytest -p no:cacheprovider -q` 全绿

## 3. 前端"本月账本"卡片

- [x] 3.1 `frontend/src/views/Dashboard.vue`：`emptyDashboard` 增加 `month_summary: null` 缺省；在行情可信摘要之后、待处置队列之前渲染卡片（`v-if="dashboard.month_summary"` 守卫）
  **验收**：旧 payload（无 month_summary）不渲染卡片、不报错
- [x] 3.2 卡片内容：主导数字 = `month_summary.realized_profit_loss`（`formatMoney` + 盈亏着色）+ "平仓 N 笔"；辅助行 = 本月触发 N 次 · 调整止损 N 次（调低 M）+ 当前浮亏参考（复用 `unrealized_profit_loss`，标注"当前快照"）；`largest_loss` 非空显示"最大亏损来源"；待处置 > 0 时"去处置"按钮路由 `/alerts`
  **验收**：三个视口（桌面/平板/手机）下布局正确，沿用既有 panel 变量与响应式规则
- [x] 3.3 mount 测试（mock `../src/api`）：含 `month_summary` → 主导数字/辅助行/去处置按钮渲染且数值正确；`month_summary: null` → 不渲染；全零 → 零值展示
  **验收**：`npm test` 中新增用例通过

## 4. E2E 场景

- [x] 4.1 在 `frontend/tests/e2e/supported-runtime.spec.js` 增加场景：用唯一名称 seed 一笔持仓并走真实平仓流程，`page.request.get('/api/dashboard')` 取 `month_summary.realized_profit_loss` 与 `closed_count`，断言卡片文本与 API 值一致（不断言绝对值，规避共享 e2e.db 累积）；`assertPageIntegrity` 通过
  **验收**：`npm run test:e2e` 全场景（含既有 8 个）通过

## 5. 文档与门禁

- [x] 5.1 README「核心能力/仪表盘」章节补充"本月账本"卡片说明（本月已实现盈亏、触发与调整统计、最大浮亏来源；明确已实现与浮亏不合并）
  **验收**：README 与实际行为一致
- [x] 5.2 运行 `.\verify.ps1` 全量门禁并修复所有回归
  **验收**：门禁全部通过
- [x] 5.3 `/opsx:sync` 同步 delta spec 进主 specs 后 `/opsx:archive`
  **验收**：主 spec `openspec/specs/dashboard/spec.md` 含新需求；change 归档
