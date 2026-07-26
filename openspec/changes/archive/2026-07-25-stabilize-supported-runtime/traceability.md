# Requirement 到测试可追溯表

| Capability / Requirement | 自动化证据 |
|---|---|
| alert-system / Separate reading and disposition actions in UI | `frontend/tests/alerts-routing.mount.spec.js`；`frontend/tests/e2e/supported-runtime.spec.js` |
| dashboard / Return Decimal-safe portfolio accounting summaries | `backend/tests/test_api.py::test_dashboard_mixed_portfolio_and_today_alert`；`backend/tests/test_supported_runtime.py::test_dashboard_keeps_holding_as_authority_when_shadow_exists` |
| dashboard / Holdings overview list | `frontend/tests/supported-views.mount.spec.js`；三视口 E2E |
| data-portability / 可移植格式无法表示权威事实时默认拒绝 | `backend/tests/test_supported_runtime.py::test_disabled_csv_and_webhook_calls_do_not_write` |
| frontend-shell / 每个可见命令都必须指向受支持工作流 | 告警路由挂载测试；三视口 E2E 的路由与控制台断言 |
| frontend-shell / Request privileged capabilities on demand | `frontend/tests/notification-permission.test.js`；Settings 挂载测试 |
| holdings-crud / 使用 legacy 持仓工作流作为稳定版本运行面 | `backend/tests/test_api.py`；`backend/tests/test_supported_runtime.py`；三视口 E2E |
| local-operations / Migrate through explicit authority stages | `backend/tests/test_shadow_projection.py`；`backend/tests/test_supported_runtime.py::test_cutover_is_rejected_before_any_side_effect` |
| local-operations / 安全的本地进程生命周期 | `backend/tests/test_operations.py`；`start.ps1` 依赖预检；`verify.ps1` |
| notification-delivery / 只暴露具有有效 owner 的投递路径 | `backend/tests/test_supported_runtime.py`；监控全套测试验证站内告警不依赖投递 |
| price-fetching / Scheduled price monitoring | `backend/tests/test_monitoring.py`；`backend/tests/test_monitoring_trust.py` |
| price-fetching / Manual price refresh API | `backend/tests/test_supported_runtime.py` 的两个入口错误矩阵；三视口 E2E |
| quality-gates / 可复现的验证命令 | `verify.ps1` 连续两次执行证据 |
| quality-gates / 本地端到端冒烟测试 | `scripts/smoke.py` |
| quality-gates / Mount real frontend components | `frontend/tests/*.mount.spec.js` |
| quality-gates / Validate core journeys in target viewports | `frontend/tests/e2e/supported-runtime.spec.js` 的三个 Playwright project |
| quality-gates / Test extension isolation and security | `backend/tests/test_supported_runtime.py`；Settings 挂载与 E2E 隐藏断言 |
| quality-gates / Test import export and recovery boundaries | `backend/tests/test_backup_recovery.py`；`scripts/restore_drill.py` |
| runtime-settings / Group settings by operational responsibility | `backend/tests/test_api.py::test_runtime_settings_defaults_validation_and_persistence`；Settings 挂载测试 |

源码文本断言仅用于低成本结构检查；所有行为要求均同时具有 API、真实组件、浏览器或恢复演练证据。
