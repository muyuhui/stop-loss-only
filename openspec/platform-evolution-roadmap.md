# Stop-Loss Platform Evolution Roadmap

本路线图保留原 `evolve-stop-loss-platform` 总体方向，但不作为可执行 change。实施工作拆为四个按顺序交付和归档的 OpenSpec change：

原始完整 proposal、design、specs 和 tasks 保留在 Git commit `11a9760`，用于追溯拆分前的设计背景；本文件是拆分后的路线图入口。

1. `harden-monitoring-trust`：修复行情可信度、离线测试、监控诊断和并发触发一致性。
2. `introduce-position-domain`：引入正交仓位状态、批次核算、事件历史和受控事实源切换。
3. `redesign-risk-workflows`：基于稳定 API 重做风险优先的仪表盘、仓位和告警工作流。
4. `extend-local-platform`：增加可选通知、数据可移植性、保留清理和本地运维能力。

## Product Boundary

- 本地单用户运行，默认仅监听 loopback。
- 不连接券商、不保存券商凭证、不自动下单。
- 不增加止盈、云同步、多用户或公网部署。
- 行情不可信时宁可明确显示未知，也不得使用占位、过期或无法证明时点的价格触发止损。
- 站内告警和仓位事实不得依赖外部通知投递成功。

## Delivery Rules

- 每个 change 必须在完整门禁通过并归档后，后续 change 才能开始实施。
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
