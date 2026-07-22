## Context

该 change 是拆分路线的第一阶段，直接建立后续所有迁移和 UI 工作依赖的可信基线。当前 `Holding.current_price` 不能完整表达占位价、行情时间和可行动性，调度与手动刷新可能并发，fixture 路径还可能触发真实日历调用。

## Goals / Non-Goals

**Goals:**

- 每个价格都能解释来源、时点、新鲜度和是否可触发。
- 每个监控响应只报告数据库已提交事实。
- 必选门禁完全离线且网络误用立即失败。
- 单标的失败不回滚其他标的，手动与调度全量周期互斥。

**Non-Goals:**

- 不引入 position/lot 新领域模型。
- 不实现部分平仓、重新布防 UI、Webhook 或导入导出。
- 不承诺免费数据源具有交易级实时性。

## Decisions

### 1. 行情状态由后端统一裁决

内部使用 `unpriced/live/delayed/close/nav/stale/error`，同时返回 `source`、`quoted_at`、`fetched_at`、`fresh_until`、`is_actionable` 和稳定错误码。前端不得自行推断可行动性。相比继续使用 nullable 时间和页面推断，该方案能让触发策略集中且可测试。

### 2. Provider 与交易日历都使用可注入端口

生产适配器封装 akshare，测试适配器只读取内存 fixture。fixture 模式禁止导入或调用真实 provider。交易日历按市场和日期缓存；失败时只允许使用未过期缓存或带 `degraded` 标识的有限降级。

日历来源分为 `authoritative`、`valid_cache` 和 `weekday_fallback`。前两者可以参与交易时段裁决；`weekday_fallback` 只允许系统继续取价和记录诊断，默认不得让行情可行动。只有行情提供方自身给出可验证的当前交易日与当前交易时段时间，才能在 weekday fallback 周期中把该行情裁决为可行动。

### 3. 周期摘要与标的结果分层提交

监控周期先建立 cycle，行情规范化后逐标的在 savepoint 内处理，最终提交周期摘要。捕获单标的失败后继续处理其他标的；任何未捕获异常仍回滚整个外层事务。响应在提交后重新读取 cycle、仓位和告警构造。

### 4. 乐观并发和稳定幂等键

沿用 SQLite，使用版本条件更新而非行级锁。触发幂等键基于当前 holding、规则指纹和触发序列；唯一冲突后重新读取数据库事实。手动全量刷新与调度刷新使用进程内互斥，超时返回稳定 busy 错误，不启动第二轮下载。

### 5. P0 门禁先于领域迁移

先固化现有 API fixture，再增加网络哨兵、provider 契约、并发事务和离线 smoke。只有本 change 完整通过并归档后，才能应用 `introduce-position-domain`。

## Risks / Trade-offs

- [单枚举仍不能描述所有 provider 细节] → 保留原始类型映射诊断，但领域只消费规范化状态。
- [savepoint 使用不当仍可能导致外层回滚] → 测试混合成功、唯一冲突和数据库忙，响应从提交后数据重建。
- [进程内互斥不能支持多进程] → 本阶段明确只支持单进程、单调度器部署。
- [日历降级可能误判交易状态] → 记录日历来源；weekday fallback 只允许取价和诊断，除非行情自身证明当前交易时点，否则不得触发。

## Migration Plan

1. 固化 API、数据库和完全离线基线。
2. 增加兼容列和 `monitoring_cycles`，旧字段继续可用。
3. 切换 provider/日历适配层，再切换监控事务与响应构造。
4. 增加轻量监控状态和行情状态展示。
5. 回滚时恢复旧服务路径；新增诊断表和向后兼容列可保留。

## Open Questions

- 无阻塞问题。休市收盘价默认不可自动触发；若未来允许用户覆盖，另建 change。
