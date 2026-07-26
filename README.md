# 止损不止盈

一个面向 A 股和基金的本地持仓止损监控工具。系统只提供行情记录、止损计算和告警，不连接券商，也不会自动下单。

## 核心能力

- 固定价格、买入价百分比、移动止损三种规则。
- A 股交易日和早/午盘时段判断，批量行情获取与新鲜度校验。
- `holding → triggered → closed` 生命周期，明确区分“触发信号”和“确认成交”。
- 告警快照、当前/已实现收益仪表盘、运行时轮询设置。
- 持仓详情按 1 月、3 月、6 月或 1 年展示日级价格走势、买入价和止损警告线。
- SQLite 版本化迁移、校验和备份恢复、结构化日志和分层测试。

## 技术栈

- 后端：Python、FastAPI、SQLAlchemy、SQLite、APScheduler、akshare
- 前端：Vue 3、Element Plus、Pinia、Vite

## 安装

依赖安装与服务启动相互独立：

```powershell
# 仅运行依赖
.\setup.ps1

# 包含测试依赖
.\setup.ps1 -Dev
```

## 正常启动与停止

```powershell
.\start.ps1
.\stop.ps1
```

正常模式会：

- 在启动后端前显式执行数据库迁移；旧数据库迁移前自动备份。
- 后端和前端只监听 `127.0.0.1`，默认端口分别为 8001、5173。
- 后端使用单 worker、无 reload，且只启动一个调度器。
- 端口被占用时报告所有者并退出，绝不终止无关进程。
- 停止时只终止 PID、启动时间和项目记录均匹配的自有进程。
- 在创建任何服务进程前验证后端导入和 `package-lock.json` 对应的完整前端依赖图；依赖不完整时按提示重新运行 `./setup.ps1`。

访问地址：

- 前端：http://127.0.0.1:5173
- API：http://127.0.0.1:8001
- OpenAPI：http://127.0.0.1:8001/docs
- Liveness：http://127.0.0.1:8001/api/health/live
- Readiness：http://127.0.0.1:8001/api/health/ready

## 开发模式

```powershell
.\dev.ps1
```

开发模式启用后端 reload，但默认关闭定时行情监控，避免重载子进程重复运行调度任务。需要验证行情时优先使用设置页的手动刷新。

## 数据库迁移与恢复

项目使用内置的有序 `schema_migrations` runner，而非 Alembic：每个整数 revision 幂等执行、记录最高已应用版本，并在升级前为旧库创建备份。该 runner 是本地 SQLite 单进程部署的 revision authority；迁移逻辑必须保持可重入并由自动化升级/降级测试覆盖。

```powershell
cd backend
python db_admin.py status
python db_admin.py upgrade
python db_admin.py downgrade
cd ..

.\backup.ps1
.\restore.ps1 -Backup <备份.db> -Manifest <备份.json>
```

恢复前必须停止后端。恢复命令会校验 SHA-256、SQLite 完整性和 manifest，再替换数据库。

## 质量门禁

```powershell
.\verify.ps1
```

验证命令为每次运行创建独立临时根目录，依次执行依赖预检、后端离线测试、前端真实组件测试、生产构建与包体预算、三视口浏览器 E2E、离线 API/进程 smoke、恢复演练以及全部当前 OpenSpec 严格校验。默认测试不访问真实行情网络；真实 akshare 验证应在交易时段手动执行，并与必选门禁分开记录。

## 日志与排障

- 正常启动日志位于 `logs/`，默认保留，不会在停止时删除。
- 应用日志只记录关联 ID、周期 ID、状态、耗时和聚合计数，默认不记录价格、数量、成本或完整响应体。
- liveness 成功但 readiness 失败：先运行 `python backend/db_admin.py status`，再按提示迁移。
- 行情部分失败：检查刷新响应中的逐标的 `error`、`fresh`、`source` 和时间字段。
- 历史走势首次打开时通过 AkShare 获取股票日线或基金净值并写入 `price_history` 缓存，后续仅补充缺失日期；外部服务失败时会继续展示已有缓存并提示可能过期。
- 固定价格和百分比止损显示水平线，移动止损显示只升不降的阶梯线；历史止损线按当前止损配置计算，不代表过去真实配置记录。
- 历史图表无数据或加载失败时，可在图表区域单独重试，不影响修改止损、刷新当前价格和平仓操作。
- 调度器未运行：确认使用正常启动模式，检查 readiness 的 `scheduler_running` 和已保存监控间隔。
- 建议定期备份；默认备份目录为 `backend/backups/`，日志与备份保留周期由使用者按磁盘情况管理。

## 行情可信度与监控诊断

- 新持仓初始状态为 `unpriced`，买入成本不会再伪装成当前行情。行情状态由后端统一裁决为 `unpriced`、`live`、`delayed`、`close`、`nav`、`stale` 或 `error`。
- 只有响应中 `is_actionable=true` 的新鲜行情才能触发止损；休市收盘价、过期价、失败结果以及无法由权威日历或提供方时间证明的工作日降级行情均不可触发。
- `GET /api/monitoring/status` 提供调度状态、下一次运行、最近周期、最近成功、行情覆盖率和稳定原因码；`GET /api/monitoring/cycles` 支持 `page`、`size`、`status` 和 `kind` 筛选。
- `POST /api/prices/refresh` 保持兼容，并可通过 `holding_id` 或 `code` 查询参数限定范围；`POST /api/prices/{code}/refresh` 提供标的级快捷入口。
- 监控周期只记录状态、时间、覆盖率、聚合计数和稳定错误码，不保存价格、数量、成本或提供方原始响应。
- 当前只支持单进程、单 worker、单调度器运行。调度刷新与手动刷新由进程内有界互斥锁协调；不要将该锁视为多进程协调机制。

## 受支持运行面

当前稳定版本有意收缩到 legacy `Holding` 权威模型：

| 运行面 | 当前状态 |
|---|---|
| Holding 创建、列表、详情、止损修改、整笔手动平仓 | 支持 |
| 仪表盘、价格与历史、定时/手动监控 | 只读取并更新 Holding |
| 告警 | 支持站内快照和已读；处置入口进入 `/holdings/:id` |
| `shadow-read`、shadow 重建与对账 | 支持只读迁移诊断 |
| SQLite 备份、停服恢复、隐私安全诊断 | 支持 |
| Position 创建、加仓、部分平仓、确认、重新布防 | 推迟，HTTP 返回 `409 feature_not_supported` |
| CSV 导入导出 | 推迟，HTTP 返回 `409 feature_not_supported` |
| Webhook、浏览器系统通知、retention 控制 | 推迟，不在稳定 UI 显示且后端拒绝修改 |

`legacy` 和 `shadow-read` 是当前仅有的受支持权威阶段，两者都只向 Holding 写入。可运行 `python backend/db_admin.py shadow-enable`、`shadow-rebuild` 和 `shadow-status` 维护诊断投影。`python backend/db_admin.py cutover` 会在备份或数据库修改前以 `cutover_not_supported` 拒绝，不存在可用于绕过该边界的稳定开关。

如果数据库已经处于 `new-authoritative`，应用 readiness 会返回 503 且不会启动调度器。请停止服务，找到切换前生成并验证过的 `.db` 与 `.json` manifest，然后运行：

```powershell
python backend/db_admin.py restore <backup.db> <manifest.json>
```

恢复后重新运行 readiness 和 `./verify.ps1`。系统不会自动把 Position 反向投影到 Holding，以免静默改变财务事实。

## 风险工作流

- 只有界面标记为可行动的行情可以触发止损；延迟、过期、未定价和错误行情只用于诊断。
- 将告警标记为已读只清除未读状态，不会关闭持仓或改变触发事实。
- 告警中的“查看持仓”进入 legacy 持仓详情，手动平仓需要单独确认并记录实际成交价。
- 当前只支持整笔关闭 Holding；Position 批次、FIFO 分配和部分平仓保留在后续平台 change 中。

## Risk budget and position planner

- Risk planning is available only after the position domain reaches
  `new-authoritative`. It never writes to the legacy holdings path.
- Portfolio equity is a manually maintained planning input, not a live broker
  balance. Update it after deposits, withdrawals, or material account changes.
- The default policy is a 5% portfolio stop-risk ceiling and a 1% per-position
  ceiling. Position risk cannot exceed the portfolio percentage.
- Covered portfolio risk is the sum of each open position's estimated loss at its
  active stop: `max(0, remaining_cost + estimated_exit_cost -
  stop_price * remaining_quantity)`. This calculation does not require a current
  actionable quote; valuation coverage and stop-risk coverage are reported
  separately.
- If any open position lacks a calculable active stop, remaining risk capacity is
  indeterminate and the planner does not recommend a quantity.
- A plan uses the tighter of per-position risk and remaining portfolio capacity,
  subtracts the user's fixed entry and exit fee estimates, and rounds down. Normal
  A-share openings use 100-share lots; funds use up to six quantity decimals.
- The planner reports required capital but cannot verify broker cash. A preview is
  advisory, reserves no capacity, places no order, and creates no position. The
  user must continue to a separate position form and explicitly submit it.

### v4 回滚

1. 先运行 `./stop.ps1`，再使用 `./backup.ps1` 创建可恢复备份。
2. 在 `backend` 目录运行 `python db_admin.py downgrade`，将迁移版本从 4 回退为 3。
3. 回退应用代码并重新启动。v4 新增列、索引和 `monitoring_cycles` 表会保留，旧代码会忽略它们，避免破坏诊断历史。
4. 若需恢复数据，保持后端停止并使用 `./restore.ps1 -Backup <backup.db> -Manifest <backup.json>`。
