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

## 环境要求

- Python 3.12 或更高版本，`python` 需在 PATH 中（`setup.ps1` 会预检版本）。
- Node.js 20.19+ 与 npm 7+（前端依赖通过 `npm ci` 安装）。
- openspec CLI（`npm install -g @fission-ai/openspec`）：仅运行完整验证门禁 `.\verify.ps1` 时需要；`setup.ps1` 会预检其可用性。

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
- 固定价格和百分比止损显示水平线，移动止损显示只升不降的阶梯线；图表止损线按当前止损配置计算，每次创建与修改止损的真实快照可在持仓详情"止损调整记录"中追溯（删除持仓后仍保留）。
- 仪表盘展示交易时段徽标（盘前/交易中/午休/已收盘，来源为 `/api/monitoring/status` 的 `market_session`）；时段指示只表达时间语义，不判定周末与节假日。持仓卡片与详情页展示行情时效（"刚刚"/"N 分钟前"/本地时间），未定价或行情不可用时显示"未定价/行情不可用"，不会显示虚假时效。
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
| 浏览器系统通知 | 支持（站内呈现，仅本机） |
| Webhook、retention 控制 | 推迟，不在稳定 UI 显示且后端拒绝修改 |

`legacy` 和 `shadow-read` 是当前仅有的受支持权威阶段，两者都只向 Holding 写入。可运行 `python backend/db_admin.py shadow-enable`、`shadow-rebuild` 和 `shadow-status` 维护诊断投影。`python backend/db_admin.py cutover` 会在备份或数据库修改前以 `cutover_not_supported` 拒绝，不存在可用于绕过该边界的稳定开关。

**浏览器系统通知（仅本机呈现）**：新触发止损时，页面在检测到此前未通知过的未读告警后发送一条浏览器通知，并可在标签页隐藏期间通过降频轮询继续检测。通知权限只在设置页显式开启通知时于用户手势中请求，页面加载绝不主动请求；权限被拒或浏览器不支持时降级为标签标题未读徽标与站内告警列表，核心流程不受影响。通知偏好（开关、提示音）保存在浏览器 localStorage，与后端设置无关；同一条告警只通知一次，通知发送失败静默处理。

如果数据库已经处于 `new-authoritative`，应用 readiness 会返回 503 且不会启动调度器。请停止服务，找到切换前生成并验证过的 `.db` 与 `.json` manifest，然后运行：

```powershell
python backend/db_admin.py restore <backup.db> <manifest.json>
```

恢复后重新运行 readiness 和 `./verify.ps1`。系统不会自动把 Position 反向投影到 Holding，以免静默改变财务事实。

## 风险工作流

- 只有界面标记为可行动的行情可以触发止损；延迟、过期、未定价和错误行情只用于诊断。
- 将告警标记为已读只清除未读状态，不会关闭持仓或改变触发事实。
- 触发后的处置闭环：仪表盘“待处置持仓”队列与待处理告警的“去处置”入口直达持仓详情；已触发持仓可选择**重新布防**（按新规则恢复监控，待处理告警标记为“已重新布防”，止损调整历史写入 `rearm` 来源，重新布防后若现价仍低于新止损价将在下一监控周期再次触发并产生新告警）或**手动平仓**（单独确认并记录实际成交价）。
- 告警中的“去处置/查看持仓”进入 legacy 持仓详情；手动平仓需要单独确认并记录实际成交价。
- 当前只支持整笔关闭 Holding；Position 批次、FIFO 分配和部分平仓保留在后续平台 change 中。

## 可信展示与告警查询契约

- `HoldingResponse.profit_loss_pct` 和 `stop_loss_distance_pct` 是可空字段。持仓处于 `unpriced` 且没有可估值行情时返回 `null`；前端显示“未定价”和“风险未知”，不会将空值转换为 `0.00%`、临近止损或安全状态。
- `GET /api/monitoring/status` 在没有活动持仓作为分母时，将 `actionable_quote_coverage_pct`、`valuation_quote_coverage_pct` 和兼容字段 `quote_coverage_pct` 返回为 `null`。存在活动持仓但均未覆盖时返回真实的 `0%`。
- `GET /api/alerts` 支持 `search`、`unread`、`disposition`、`page` 和 `size`。搜索匹配不可变的持仓名称/代码快照并在分页前执行；`unread=false` 明确筛选已读告警；处置状态仅接受 `triggered`、`closed`、`rearmed`。
- 历史空处置状态在响应和 `triggered` 筛选中按待处理解释。手动关闭 legacy 持仓会在同一业务事务中把相关待处理告警更新为 `closed`，但不会修改阅读状态和触发快照。
- 风险预算读取或风险试算能力不可用时，仪表盘和设置页不展示对应区域，也不会请求可选风险接口或提交隐藏的风险政策字段。直接访问 `/planner` 仍显示明确的不可用状态。

## 风险预算与买入风险试算

- 稳定的 `legacy` 与 `shadow-read` 运行面支持只读风险预算、新仓风险试算和活动 Holding 的加仓风险试算。两者仍以 Holding 为权威事实，不开启 Position 创建、批次、部分平仓或其他 Position 生命周期写入。
- 组合权益是手工维护的试算输入，不是券商实时余额。默认政策为组合止损风险上限 5%、单笔风险上限 1%；入金、出金或权益发生较大变化后应重新维护并试算。
- legacy Holding 的当前止损风险口径为 `max(0, (buy_price - stop_loss_price) * quantity)`。Holding 不保存历史交易费用，因此系统不会补造历史费用；新仓或加仓计划中明确填写的买入与退出费用会计入本次增量风险。
- `shadow-read` 只计算 legacy Holding，不会把对应 shadow Position 重复计入。隔离的 `new-authoritative` API 仍按 Position 剩余成本、剩余数量、活动止损和预计退出费用计算。
- 任一活动权威记录缺少可计算数量、成本或止损价时，剩余风险容量为未知，系统不返回数量。风险覆盖与行情估值覆盖彼此独立，止损风险计算不要求当前行情可行动。
- 新仓和加仓都使用单笔剩余容量与组合剩余容量中更严格的一项，扣除明确费用后向下取整。A 股按 100 股取整，基金数量最多保留六位小数，结果统一称为“风险约束下的最大数量”。
- 加仓风险试算始终沿用 Holding 当前持久化止损价，不重算百分比止损、不放宽止损，也不重置移动止损最高价；若要调整止损，应先通过独立止损流程修改，再重新试算。
- 风险试算只回答在给定输入下最多能承受多少止损风险，不判断标的是否值得买，不预测收益，不生成推荐标的。系统无法验证券商可用现金，不预留风险容量、不下单、不创建或修改持仓，也不记录实际加仓；采取任何行动前需要用最新数据重新试算并自行复核资金。

## DeepSeek 持仓复盘

- 在“设置”页的“DeepSeek 持仓复盘”中保存 API Key。Key 使用当前 Windows 用户的 DPAPI 加密后保存在本机文件中，不进入 SQLite、日志、诊断或数据库备份；设置读取只显示是否已配置。替换和清除都在同一区域完成。
- “检测连接”是可选的真实网络请求，只发送最小检测内容，不包含持仓数据。强制测试使用离线 fixture，不会连接真实 DeepSeek；真实检测失败也不会清除已经保存的 Key。
- 活动持仓详情的“更新行情并 AI 复盘”会先运行现有单持仓行情刷新，再读取更新后的 Holding，最后生成复盘。AI review API 本身不会运行监控周期，也不会修改持仓、止损、告警、设置或订单；只可能补齐 `price_history` 技术缓存。
- 发送到 DeepSeek 的范围限于目标持仓事实、当前行情、最近 90 个自然日内最多 60 个有效日线/净值点、既定止损和聚合组合风险。金额、收益、回撤、区间位置和风险容量均由本地后端确定性计算，模型只负责归纳解释。
- 少于 20 个历史点时只生成低可信风险复盘，不判断近期趋势；完全没有历史行情时拒绝复盘。已有缓存足够但更新失败时可以降级使用缓存，并显示最后交易日和数据局限。
- 复盘动作受固定枚举和本地规则约束。已触发止损会强制显示“执行既定止损”；加仓相关结果最多引导进入现有只读风险试算，不给数量、不代表推荐买入，也不会自动交易。复盘不包含新闻、财报、行业研究、券商余额或未来价格预测。
- 常见稳定错误码：`ai_not_configured`（未配置）、`ai_review_busy`（同持仓已有请求）、`market_data_not_ready`（当前行情不可用）、`history_data_unavailable`（无历史行情）、`ai_timeout`、`ai_rate_limited`、`ai_unavailable` 和 `ai_response_invalid`。错误后可保留原持仓页面继续修改止损或手动平仓，并按提示重试。
- DeepSeek 首次返回的 JSON 若不符合结构或引用了不存在的事实，后端会携带完整输出契约和脱敏错误位置自动纠正一次，因此单次复盘最多可能产生两次 Provider 调用。纠正不会放宽本地事实校验，不会记录模型原文，也不会产生持仓、止损或订单写入。
- Provider 固定为 DeepSeek 官方 HTTPS API，第一版不支持其他 Provider 或自定义 Base URL。默认模型和超时可由应用环境配置维护，但不会在设置页开放任意地址。

### 回滚

1. 先运行 `./stop.ps1`，再使用 `./backup.ps1` 创建可恢复备份。
2. 在 `backend` 目录运行 `python db_admin.py status` 确认当前迁移版本，再运行 `python db_admin.py downgrade` 将迁移版本回退一级。
3. 回退应用代码并重新启动。downgrade 是非破坏性的：新增列、索引和表会保留，旧代码会忽略它们，避免破坏诊断历史。
4. 若需恢复数据，保持后端停止并使用 `./restore.ps1 -Backup <backup.db> -Manifest <backup.json>`。

最新 schema 版本以 `backend/migrations.py` 的 `LATEST_SCHEMA_VERSION` 为准，本说明不硬编码具体版本号。
