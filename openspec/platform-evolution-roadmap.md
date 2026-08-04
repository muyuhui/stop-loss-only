# Stop-Loss Platform Evolution Roadmap

本路线图保留原 `evolve-stop-loss-platform` 总体方向，但不作为当前稳定版本的能力声明。已归档 change 记录历史设计和实现尝试；当前受支持边界由 `stabilize-supported-runtime` 收缩并重新验证。

原始完整 proposal、design、specs 和 tasks 保留在 Git commit `11a9760`，用于追溯拆分前的设计背景；本文件是拆分后的路线图入口。

1. `harden-monitoring-trust`：修复行情可信度、离线测试、监控诊断和并发触发一致性。
2. `introduce-position-domain`：已建立 shadow 数据结构；Position 权威切换与写工作流尚未成为稳定能力。
3. `redesign-risk-workflows`：legacy Holding 的风险优先界面可用；Position 处置流程继续推迟。
4. `extend-local-platform`：数据结构和服务原型保留；CSV、Webhook 和 retention 尚无完整运行时 owner，因此稳定版本默认拒绝。浏览器系统通知已由 `notify-on-trigger` 补齐 owner（运行中的前端浏览器上下文），以站内告警事实的站内呈现方式恢复支持（仅本机）。

## 当前稳定化边界

- `legacy` / `shadow-read` 继续以 Holding 为唯一权威事实源。
- Position 表与 shadow 重建/对账保留用于迁移诊断，但不提供公共写入或 cutover。
- CSV 可移植性、外部通知投递（Webhook）和 retention 必须分别通过新的 OpenSpec change、真实 worker 所有权和 E2E 后才能重新上线；浏览器系统通知只呈现站内告警事实，不依赖外部投递成功。
- 已经处于 `new-authoritative` 的数据库必须恢复切换前备份；禁止自动反向投影。

## Product Boundary

- 本地单用户运行，默认仅监听 loopback。
- 不连接券商、不保存券商凭证、不自动下单。
- 不增加止盈、云同步、多用户或公网部署。
- 行情不可信时宁可明确显示未知，也不得使用占位、过期或无法证明时点的价格触发止损。
- 站内告警和仓位事实不得依赖外部通知投递成功。

## Delivery Rules

- 每个未来 change 必须在完整门禁通过并归档后，能力才可加入受支持运行面。
- 迁移和兼容行为以各 change 的 design、specs 和 tasks 为准，本路线图不重复定义可执行要求。
- 旧 HTTP API 的移除、成本方法切换、高级止损策略和其他新增范围必须分别建立后续 change。

## Dependency Chain

```text
harden-monitoring-trust
        |
        v
introduce-position-domain
        |
        v
redesign-risk-workflows
        |
        v
extend-local-platform
```
