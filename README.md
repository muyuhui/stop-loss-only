# 止损不止盈

一个面向 A 股和基金的本地持仓止损监控工具。系统只提供行情记录、止损计算和告警，不连接券商，也不会自动下单。

## 核心能力

- 固定价格、买入价百分比、移动止损三种规则。
- A 股交易日和早/午盘时段判断，批量行情获取与新鲜度校验。
- `holding → triggered → closed` 生命周期，明确区分“触发信号”和“确认成交”。
- 告警快照、当前/已实现收益仪表盘、运行时轮询设置。
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
- 调度器未运行：确认使用正常启动模式，检查 readiness 的 `scheduler_running` 和已保存监控间隔。
- 建议定期备份；默认备份目录为 `backend/backups/`，日志与备份保留周期由使用者按磁盘情况管理。
