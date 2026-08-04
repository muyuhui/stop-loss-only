## 1. 重新布防（后端）

- [x] 1.1 `routers/holdings.py` 新增 `POST /api/holdings/{id}/rearm`：仅 `triggered`（否则 400）、复用 `StopLossEngine.validate`（422）、同一事务内保存新规则 + 重算止损价 + 状态回 `holding` + `trigger_sequence`/`version` 递增 + 写入 `stop_rule_history`（`source='rearm'`）+ 该持仓 `disposition IN ('triggered', NULL)` 告警标记 `rearmed`
- [x] 1.2 补充后端测试：布防成功（状态/规则/历史来源/告警标记/序列版本递增）、校验失败 422 无副作用、非 `triggered` 返回 400、rearm 后再次跌破止损产生新告警（幂等键不冲突）、布防并发 CAS（版本递增使旧状态触发失败）
- [x] 1.3 运行后端测试确认通过（`python -m pytest -p no:cacheprovider -q`）

## 2. 仪表盘待处置队列

- [x] 2.1 `Dashboard.vue` 新增"待处置持仓"面板：过滤 `dashboard.holdings` 中 `status === 'triggered'`，风险区后渲染，无触发不渲染；每项显示名称/代码、当前价与止损价、状态标签 + "去处置"直达 `/holdings/:id`
- [x] 2.2 挂载测试：有 `triggered` 时渲染队列与直达入口、无 `triggered` 时不渲染

## 3. 详情页处置引导

- [x] 3.1 `HoldingDetail.vue`：`triggered` 时"修改止损"按钮变为"重新布防"（warning），保存路由到 `POST /rearm`，成功后重新加载并提示；hint 说明"布防后若现价仍低于新止损价，将在下一监控周期再次触发"；`holding` 状态仍走既有 `PUT`
- [x] 3.2 挂载测试：`triggered` 显示"重新布防"且保存调用 rearm 端点、`holding` 状态仍调用 PUT、平仓入口保留

## 4. 告警卡处置入口

- [x] 4.1 `Alerts.vue`：`disposition === 'triggered'` 的告警卡持仓链接升级为主操作"去处置"（primary），其余保持"查看持仓"
- [x] 4.2 更新受影响的既有前端测试断言（如存在）

## 5. E2E 闭环

- [x] 5.1 `frontend/tests/e2e/supported-runtime.spec.js` 新增完整闭环场景：创建持仓（止损 9）→ 刷新触发（fixture 价 8.8）→ 详情"重新布防"（新止损 8.5）→ 状态回 `holding`、原告警显示"已重新布防"、未读徽标仍在；再次刷新不产生重复告警
- [x] 5.2 运行前端全量测试与 `npm run build`，确认包体预算通过

## 6. 文档与门禁

- [x] 6.1 更新 README"风险工作流"：补充重新布防语义（处置后恢复监控、告警标记 `rearmed`、再触发产生新告警）与已读/已关闭并列
- [x] 6.2 运行 `.\verify.ps1` 全量门禁，确认后端测试、前端测试、构建、E2E、smoke、恢复演练与 OpenSpec 严格校验全部通过
- [x] 6.3 归档本 change 前，同步 delta specs 到主 specs（`/opsx:sync`），再归档（`/opsx:archive`）
