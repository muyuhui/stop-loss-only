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

验证命令依次运行：后端离线测试、前端行为测试、生产构建与包体预算、隔离端到端冒烟、OpenSpec 严格校验。默认测试不访问真实行情网络；真实 akshare 验证应在交易时段手动执行，并与必选门禁分开记录。

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

## Position domain migration

The position domain has three explicit authority stages: `legacy`, `shadow-read`, and
`new-authoritative`. During the compatibility window, legacy holdings remain the only
writer; enable shadow reads with `python backend/db_admin.py shadow-enable`, and use
`shadow-rebuild` after an interruption. Cutover is an offline operation: stop the app,
run `python backend/db_admin.py cutover`, and retain the generated verified backup.

After cutover, the new position model is authoritative and legacy holdings endpoints are
read-only compatibility DTOs for one stable release. Removing those routes requires a
separate OpenSpec change. The irreversible boundary is the cutover; rollback is performed
by stopping the app and running `python backend/db_admin.py restore <backup> <manifest>`.
FIFO is the only supported cost-basis method, and the application remains a single-process,
single-worker local deployment.

## Local platform extensions

- In-app alerts are authoritative. Browser notifications and signed webhooks are optional,
  best-effort channels and may be disabled independently.
- Browser permission is requested only after selecting the enable action. A denied or
  unsupported permission does not hide any in-app alerts.
- CSV import accepts only the standard v1 schema. Preview has no writes; commit uses the
  short-lived preview token. CSV export escapes formula prefixes and preserves Decimals.
- Backups are created in the controlled local directory. Stop the service before recovery:
  `python backend/db_admin.py restore <backup> <manifest>`. Diagnostics omit databases,
  secrets, prices, quantities, costs, and provider response bodies.

## Risk workflow guide

- Treat a quote as actionable only when the interface marks it as such; delayed,
  stale, unpriced, and error states are informational and cannot trigger a stop.
- Reading an alert only clears its unread badge. A triggered position requires a
  separate acknowledgement, rearm, or close disposition in its position detail.
- Partial closes preserve FIFO lot allocation and leave an open position in risk
  monitoring until the remaining quantity reaches zero. Closed positions are
  review-only and show their recorded events and realized results.
- The Positions and Alerts filters are stored in the URL, so the selected view is
  retained when moving between a list and a detail page.

### v4 回滚

1. 先运行 `./stop.ps1`，再使用 `./backup.ps1` 创建可恢复备份。
2. 在 `backend` 目录运行 `python db_admin.py downgrade`，将迁移版本从 4 回退为 3。
3. 回退应用代码并重新启动。v4 新增列、索引和 `monitoring_cycles` 表会保留，旧代码会忽略它们，避免破坏诊断历史。
4. 若需恢复数据，保持后端停止并使用 `./restore.ps1 -Backup <backup.db> -Manifest <backup.json>`。
