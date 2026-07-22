## Context

该 change 依赖 `harden-monitoring-trust` 已归档。当前单表模型不能表达批次、部分平仓和审计历史；现有 SQLite 数据和 HTTP 路由必须平滑迁移，且不能把功能开关误当作已写入数据的回滚机制。

## Goals / Non-Goals

**Goals:**

- 建立 instrument、account、position、lot、allocation、rule 和 event 边界。
- 正交表达仓位生命周期、风险状态和数量事实。
- 通过有序迁移、影子读取和对账切换事实来源。
- 保持旧 API 一个明确发布周期可用。

**Non-Goals:**

- 不重做完整前端信息架构。
- 不增加多用户、券商连接、外部投递或 CSV。
- 不支持在新模型成为唯一写源后直接开关降级。

## Decisions

### 1. 使用正交状态而非组合枚举

`Position.lifecycle_status` 仅为 `open/closed`；`risk_status` 为 `normal/triggered/acknowledged`。部分平仓由剩余数量和 allocation 推导，不是生命周期状态。重新布防创建新规则和新触发序列，并将风险状态恢复为 `normal`，旧事件和告警保持不可变。

### 2. 默认 FIFO，首轮不提供方法切换

批次和分配全部使用 Decimal/Numeric。为消除实施歧义，本 change 固定 FIFO；账户表预留 `cost_basis_method`，但改变方法需另建 change。前端不承担财务计算。

### 3. 有序迁移并明确事实来源阶段

迁移状态为 `legacy -> shadow-read -> new-authoritative`：

- `legacy`：只写旧模型，新表只由迁移生成。
- `shadow-read`：业务仍只写旧模型；事务提交后同步投影到新模型，任何分歧记录并阻止切换。这里不是两个并列事实来源。
- `new-authoritative`：只写新模型，旧 DTO 由新模型映射；旧表不再承诺持续同步。

不采用长期双写，因为 SQLite 下跨模型双写会扩大事务和回滚复杂度。

### 4. 切换是受控迁移，不是普通运行时开关

进入 `new-authoritative` 前必须停止调度和写请求、完成最终投影与对账、创建备份并原子更新模式。切换后回滚需要显式反向导出/恢复备份，不能仅关闭环境变量。

### 5. API 兼容按发布版本结束

新增 `/api/positions` 资源；旧 `/api/holdings` 等由兼容 DTO 映射。兼容期定义为新 API 正式发布后的一个稳定版本，移除旧 API 必须另建 change，并先记录使用情况。

## Risks / Trade-offs

- [领域迁移丢失财务精度] → 代表性数据库逐项对账 Decimal、数量、成本、状态、告警和汇总。
- [状态拆分增加查询复杂度] → 提供统一查询 DTO 和索引，不在页面自行组合业务状态。
- [旧模型无法表达部分平仓] → 部分平仓只在新模型成为事实来源后开放。
- [迁移中断留下半成品] → 每个 revision 独立、可重入检测，切换前始终可从备份恢复旧模式。

## Migration Plan

1. 选择并固化 Alembic 或等价有序执行器。
2. 创建新表并从复制的旧数据库迁移、对账。
3. 在生产副本进入 shadow-read，持续比较但仍由旧模型响应。
4. 停写、最终同步、备份、对账后切到 new-authoritative。
5. 启用新命令与 API，旧路由通过兼容 DTO 返回。
6. 切换前可删除影子表回滚；切换后只能恢复切换前备份或执行经验证的反向迁移。

## Open Questions

- 无阻塞问题。成本匹配固定 FIFO；默认账户只在数据库和设置元数据中预留，不进入首轮主界面。
