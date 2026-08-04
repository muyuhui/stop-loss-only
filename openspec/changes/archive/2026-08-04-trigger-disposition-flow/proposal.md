## Why

止损触发后的处置路径是当前最大的产品缺口：已触发持仓（`triggered`）**只能手动平仓**——`PUT /api/holdings/{id}` 拒绝非 `holding` 状态，没有"重新布防"（rearm）动作；仪表盘只显示未读告警数，没有"待处置"队列；告警卡有处置状态（待处理/已关闭/已重新布防）却缺少直达处置的入口。用户触发后要"仪表盘 → 告警 → 详情 → 平仓"四跳才能完成一件事，且"评估后继续监控"这一选择根本不存在。告警处置状态三角（`triggered`/`closed`/`rearmed`）中 `rearmed` 在 legacy 域从未被写入。

## What Changes

- **重新布防（legacy rearm）**：新增 `POST /api/holdings/{id}/rearm`，仅 `triggered` 持仓可用——校验新止损规则（422）、重算止损价、状态回到 `holding`、`trigger_sequence` 与 `version` 递增（保证下次触发产生新的幂等生命周期）、把该持仓待处理告警的处置状态改为 `rearmed`、写入 `stop_rule_history`（来源 `rearm`），全部同一事务。
- **仪表盘待处置队列**：存在已触发持仓时，仪表盘在风险区后展示"待处置持仓"面板，列出已触发持仓与"去处置"入口（直达详情），不再依赖未读告警数间接表达。
- **详情页处置引导**：`triggered` 持仓的"修改止损"按钮变为"重新布防"，保存走 rearm 端点并在成功后刷新状态；平仓入口保持不变；处置后历史与告警时间线一致。
- **告警卡处置入口**：待处理（`triggered`）告警的持仓链接升级为主操作"去处置"；`rearmed` 处置状态在详情与历史中可读。
- **测试**：后端 rearm 生命周期/幂等/告警处置/历史测试（含 rearm 后再次触发产生新告警）；前端挂载测试（队列渲染、详情 rearm 流程）；E2E 完整闭环（触发 → 重新布防 → 状态回到 holding、告警显示已重新布防）。

## Capabilities

### New Capabilities

（无新增能力——legacy 处置闭环补全既有域）

### Modified Capabilities

- `stop-loss-engine`: 触发生命周期支持"重新布防后重新触发"——rearm 递增触发序列，使下一次跌破止损产生新的告警生命周期。
- `alert-system`: `rearmed` 处置状态由 rearm 动作写入；待处理告警提供直达处置的入口。
- `holdings-crud`: 新增 legacy 重新布防端点（状态约束、校验、历史记录）；详情页处置引导。
- `dashboard`: 呈现"待处置持仓"队列与直达入口。

## Impact

- **后端**（小）：`routers/holdings.py` 新增 rearm 端点（复用 `StopLossEngine`/`_commit_legacy`/`stop_rule_history` 写入）；`routers/alerts.py` 无变化（`rearmed` 已可筛选）。无数据库迁移。
- **前端**（中）：`Dashboard.vue`（待处置面板）、`HoldingDetail.vue`（triggered 处置区 + rearm 保存流）、`Alerts.vue`（去处置入口）。
- **测试**：后端 rearm 生命周期/幂等/告警处置/历史测试（含 rearm 后再次触发产生新告警）；前端挂载测试（队列渲染、详情 rearm 流程）；E2E 完整闭环（触发 → 重新布防 → 状态回到 holding、告警显示已重新布防）。
- **文档**：README"风险工作流"补充重新布防语义（与已关闭、已读并列）。
- **风险与边界**：不改变触发判定与告警事实；rearm 只影响该持仓后续生命周期；删除已触发持仓仍被禁止；`rearmed` 处置标记不改阅读状态。
