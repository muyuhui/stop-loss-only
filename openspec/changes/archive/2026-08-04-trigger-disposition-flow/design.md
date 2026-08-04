## Context

legacy 持仓生命周期 `holding → triggered → closed` 缺少第三条处置路径。现状：

- `PUT /api/holdings/{id}` 只允许 `holding` 状态修改止损（400 契约被测试固化），`triggered` 持仓只能通过 `POST /holdings/{id}/close` 平仓。
- 触发写入（`services/monitoring.py:229`）只在 `status == "holding"` 时发生，用 `trigger_sequence` 生成幂等生命周期键 `_trigger_key(holding, sequence)`；rearm 后若序列不递增，下一次跌破止损会命中幂等约束而静默不产生新告警。
- 告警处置状态 `triggered`/`closed`/`rearmed` 在 `GET /api/alerts` 筛选与前端文案中已存在（`dispositionLabel` 有"已重新布防"），但 `rearmed` 在 legacy 域从未被写入；`close_holding` 已示范"处置动作同步标记待处理告警"的模式。
- 仪表盘载荷已含 `triggered_count` 与全部持仓（含 `triggered` 项），前端无需新请求即可构建待处置队列。
- 位置域（`services/position_domain.py` rearm_position）已有 rearm 参考语义：风险状态回 normal、`trigger_sequence+1`、`version+1`。

约束：本地单用户、无数据库迁移、Decimal 金融计算、幂等生命周期不得破坏、测试 hermetic。

## Goals / Non-Goals

**Goals:**
- `triggered` 持仓可通过"重新布防"恢复监控：新止损规则、状态回 `holding`、告警标记 `rearmed`、历史记录来源 `rearm`。
- rearm 后再次跌破止损必须产生**新的**告警生命周期（新幂等键）。
- 仪表盘呈现"待处置持仓"队列，直达详情；详情页与告警卡提供明确的处置入口。
- 全部通过既有 `verify.ps1` 门禁。

**Non-Goals:**
- 不改变触发判定与告警快照字段（`stop-loss-engine` 触发语义仅扩展 rearm 后的再触发）。
- 不实现批量处置、自动平仓或任何外部投递（维持"整笔手动平仓、确认成交"的产品边界）。
- 不改 `PUT /holdings/{id}` 的状态契约（仅 `holding` 可修改止损），rearm 走独立端点。
- 不改 `delete_holding` 对 `triggered` 的禁止。

## Decisions

### D1: 独立 `POST /api/holdings/{id}/rearm` 端点，不改 PUT 契约
请求体复用 `HoldingUpdate` 的可选字段（`stop_loss_method`/`stop_loss_value`，采用与 update 相同的 prospective 合并语义，至少一个非空且组合校验通过）。**备选**：放宽 `PUT` 允许 `triggered`——破坏既有 400 契约与测试，且"修改"与"处置"语义混在一起。独立端点与位置域 `rearm_position` 命名一致，测试可独立覆盖。

### D2: rearm 事务 = 状态回 holding + 序列/版本递增 + 历史 + 告警标记
同一 `_commit_legacy` 事务内：
1. 校验状态必须为 `triggered`（否则 400）与规则（422，复用 `StopLossEngine.validate`）；
2. 写入新止损规则并重算止损价（复用 `StopLossEngine.calculate`）；
3. `status → 'holding'`，`trigger_sequence += 1`，`version += 1`；
4. 写 `stop_rule_history`（`source='rearm'`，复用既有快照行构造）；
5. 该持仓 `disposition IN ('triggered', NULL)` 的告警 → `'rearmed'`（与 `close_holding` 标记模式一致，不改 `read`）。
`trigger_sequence` 递增是本设计的正确性关键：新生命周期键使 rearm 后的再次触发产生新告警（D3）。`version` 递增使并发的进行中触发 CAS（`status=='holding' AND version==old`）失败，不会基于 rearm 前的旧状态提交。

### D3: 再触发生命周期（幂等键）
`_trigger_key(holding, sequence)` 基于 `holding.id + trigger_sequence`。rearm 递增序列后，监控周期对同一持仓的新触发将使用新键，`uq_alert_holding_lifecycle`/`uq_alert_idempotency_key` 不冲突，产生一条新告警（disposition `triggered`）。这是对 `stop-loss-engine` "每持仓触发生命周期至多一个告警"语义的补充：rearm 开启新生命周期。

### D4: 待处置队列 = 仪表盘现有载荷过滤
前端从 `dashboard.holdings` 中过滤 `status === 'triggered'` 渲染"待处置持仓"面板（空则不渲染），计数与风险区 `triggered_count` 同源。**备选**：新增 `/api/dispositions` 端点——新增调用面，收益为零。面板位置：风险 hero 之后、指标区之前（与"先看风险"层级一致），每项显示名称/代码/当前价/止损价 + "去处置"按钮直达 `/holdings/:id`。

### D5: 详情页处置引导复用编辑表单
`triggered` 持仓：按钮文案变为"重新布防"（warning 样式），进入既有 `editMode` 编辑表单；保存时按状态路由——`triggered` 调 `POST /rearm`，`holding` 调既有 `PUT`；成功后重新加载并提示（"已重新布防，恢复监控"）。面板 hint 说明"布防后若现价仍低于新止损价，将在下一监控周期再次触发"。平仓区保持不变。

### D6: 告警卡处置入口
`Alerts.vue` 卡片 footer：`disposition === 'triggered'` 时持仓链接显示为主操作"去处置"（primary），其余仍为"查看持仓"。文案复用既有 `dispositionLabel`（待处理/已关闭/已重新布防），无新文案面。

## Risks / Trade-offs

- [rearm 后现价仍低于新止损价 → 下一周期立即再触发] → 语义正确且文档/UI 明示；测试断言再触发产生**新**告警而非幂等冲突。
- [rearm 与监控周期并发竞态] → 单进程有界锁 + `version` 递增使进行中触发 CAS 失败；`trigger_sequence` 递增保证无重复键。
- [rearmed 标记覆盖用户已处置判断] → 只标记 `disposition IN ('triggered', NULL)`，已关闭/已重新布防的不重复标记；不改阅读状态。
- [用户误布防（想平仓点错）] → 布防是显式保存动作且可再平仓；详情页文案说明语义。

## Migration Plan

无数据库迁移、无 API 契约破坏（仅新增端点）。部署 = 前端 bundle + 后端同版发布：
1. 后端 rearm 端点 + 测试（生命周期/再触发/历史/告警标记）。
2. 前端队列 + 详情 rearm 流 + 告警入口，挂载与 E2E 通过。
3. README 风险工作流补充 rearm 语义。
4. 回滚：整体 revert 前端 bundle 与后端端点即可；`rearmed` 告警状态由旧版本按未知处置显示（`dispositionLabel` 兜底"待处理"），无数据破坏。

## Open Questions

- 详情页是否在处置区展示该持仓最近一条待处理告警的触发时间/触发价快照？——当前 `holding` 响应不含触发快照；若需要，可从 `GET /api/alerts?holding_id=&disposition=triggered` 取一条（前端一次轻量调用）。默认不做，先交付闭环主路径。
