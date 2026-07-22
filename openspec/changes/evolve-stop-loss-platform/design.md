## Context

### Product position

“止损不止盈”是一个面向中国 A 股和基金投资者的本地单用户风险监控工具。产品只记录持仓、拉取行情、计算止损、生成告警和记录人工处置，不连接券商、不保存券商凭证、不自动下单，也不提供投资建议。

现有系统采用 Vue 3 + Element Plus + Pinia + Vite 前端，FastAPI + SQLAlchemy + SQLite + APScheduler + akshare 后端，已经实现固定价格、百分比、移动止损，`holding -> triggered -> closed` 生命周期，响应式页面和本地运维能力。

### Current problems

1. 新建持仓使用买入价填充 `current_price`，但页面没有把占位值与真实行情区分，可能造成错误信任。
2. 股票和场内基金行情把抓取时间当作行情时间，实时、延迟和收盘状态不能被准确表达。
3. 监控周期在读取 fixture 前仍会联网获取交易日历，导致宣称离线的端到端门禁超时。
4. 手动刷新和调度刷新可能并发；告警唯一约束冲突会回滚整个事务，但返回值可能仍报告未提交的触发。
5. `Holding` 同时承担标的、交易批次、仓位、止损规则、行情状态和生命周期，难以支持加仓、部分平仓和历史复盘。
6. 触发后只有平仓路径，用户无法确认风险后重新布防，也无法记录人工覆盖原因。
7. 关闭持仓详情仍使用当前价计算“未实现盈亏”，没有完整的已实现收益、费用和持有期语义。
8. 仪表盘强调汇总金额，但没有监控健康、行情新鲜度、仓位权重、止损风险金额和预计损失。
9. 告警前端只读取默认第一页，持仓页面未使用后端已有状态筛选，历史数据增长后会静默不可见。
10. 前端测试主要验证工具函数和源码字符串，端到端冒烟只验证静态首页和 API，没有覆盖真实用户交互。

### Constraints and stakeholders

- 主要用户：在 Windows 本机使用工具的个人投资者。
- 数据敏感：持仓名称、数量、成本和损益默认不得离开本机。
- 可用性优先：行情源故障时宁可明确标记未知，也不得用过期或占位价格触发止损。
- 兼容性优先：现有 SQLite 数据、PowerShell 运维方式和 HTTP 路由必须平滑迁移。
- 资源有限：本地单进程、单调度器、SQLite 为受支持的默认部署，不引入分布式基础设施。
- 设计基准：最低支持 360px 宽视口，桌面端主要面向 1024px 以上重复操作场景。

## Goals / Non-Goals

**Goals:**

- 让每个价格都可以回答“来自哪里、代表什么时点、是否可用于触发”。
- 让每个触发和人工处置都原子、幂等、可审计、可复盘。
- 支持多批次、部分平仓、费用税费和正确的已实现/未实现收益。
- 提供风险优先、信息密度适中、桌面和手机都高效的新版界面。
- 建立历史、通知和导入导出的扩展基础，同时保持本地默认和隐私边界。
- 让必选测试完全离线，并用浏览器 E2E 覆盖核心用户旅程。
- 通过兼容 API 和版本化迁移渐进交付，避免一次性重写。

**Non-Goals:**

- 不连接券商、不自动下单、不实现模拟撮合。
- 不增加止盈功能，策略扩展仍围绕风险退出。
- 首轮不支持多用户、云同步、移动原生应用或公网部署。
- 首轮不实现完整历史行情回测平台；只保存自启用后的必要历史并预留接口。
- 不保证 akshare 或任何单一免费数据源的交易级实时性。
- 不把外部通知投递成功作为止损触发事务成功的前提。
- 不在首轮删除现有 `/api/holdings`、`/api/dashboard` 等兼容路由。

## Decisions

### 1. Adopt an evolutionary modular monolith

继续使用单 FastAPI 进程、单 SQLite 数据库和单 Vue 应用，但按领域模块划分代码：

```text
Frontend
  app-shell | dashboard | positions | alerts | history | settings
                         |
HTTP API / Compatibility DTOs
                         |
Application services
  monitoring | position accounting | alert handling | import/export
                         |
Domain
  instrument | lot | position | stop rule | quote | event
                         |
Adapters
  sqlite | akshare | market calendar | browser notification | webhook
```

选择模块化单体是因为本项目是本地单用户工具，拆微服务只会增加部署、事务和诊断成本。领域边界必须通过模块和接口体现，禁止继续把全部逻辑堆进路由或单一 ORM 模型。

替代方案：一次性重写或拆分微服务。拒绝原因是迁移风险高、对当前规模没有收益。

### 2. Separate instrument, lots, position, rule, quote and events

目标数据模型如下：

| Entity | Core fields | Responsibility |
|---|---|---|
| `Instrument` | `id`, `market`, `code`, `name`, `asset_type`, `quote_kind`, `price_scale`, `quantity_scale`, `currency` | 唯一描述可交易或可持有标的 |
| `Position` | `id`, `instrument_id`, `account_id`, `status`, `opened_at`, `closed_at`, `version` | 汇总生命周期和乐观并发版本 |
| `PositionLot` | `id`, `position_id`, `quantity`, `remaining_quantity`, `unit_cost`, `trade_date`, `fees`, `taxes` | 每次买入批次和剩余数量 |
| `CloseAllocation` | `id`, `position_id`, `lot_id`, `quantity`, `close_price`, `closed_at`, `fees`, `taxes` | 部分/全部平仓和批次成本匹配 |
| `StopRule` | `id`, `position_id`, `method`, `value`, `effective_stop_price`, `highest_price`, `status`, `version`, `effective_at` | 可版本化的当前止损规则 |
| `QuoteSnapshot` | `id`, `instrument_id`, `price`, `state`, `source`, `quoted_at`, `fetched_at`, `fresh_until`, `cycle_id` | 可解释的行情快照 |
| `PositionEvent` | `id`, `position_id`, `event_type`, `payload_json`, `actor`, `reason`, `created_at` | 不可变审计历史 |
| `MonitoringCycle` | `id`, `kind`, `market_state`, `status`, counts, timestamps, `error_code` | 一次调度或手动监控诊断 |
| `Alert` | existing snapshot + `event_id`, `rule_snapshot_json`, `position_snapshot_json`, `resolution` | 站内风险事实和处置状态 |
| `DeliveryAttempt` | `alert_id`, `channel_id`, `idempotency_key`, `status`, `attempts`, `next_retry_at` | 外部通知投递 |

`Account` 首轮只创建一个默认本地账户，但保留 `account_id`，避免未来增加多个投资账户时再次重构。账户不是用户认证边界。

所有金额、价格、数量和百分比在后端与数据库中使用 Decimal/Numeric；API 使用十进制字符串或严格 Decimal 序列化策略，前端不得依赖二进制浮点完成财务计算。

### 3. Define explicit lifecycle and disposition states

仓位生命周期：

```text
holding --fresh quote <= stop--> triggered --confirm close--> partially_closed/closed
   ^                               |
   |                               +--acknowledge + new rule--> holding
   |                               +--acknowledge only---------> triggered_acknowledged
   +-----------new effective rule--+
```

规则：

- `triggered` 表示系统检测到风险事实，不表示成交。
- “标记告警已读”只影响阅读状态，不改变仓位生命周期。
- 重新布防必须提交新规则、人工原因和确认时间，并产生 `risk_override` 与 `rule_activated` 事件。
- 重新布防不得修改旧告警快照，也不得删除旧触发事件。
- 部分平仓后，如果仍有剩余数量，用户必须选择继续使用当前规则或提交新规则。
- 关闭后禁止刷新止损或修改当前规则，但允许修改非财务备注，且产生审计事件。

不增加简单的“忽略触发并恢复”按钮，因为它会抹除风险语义。所有恢复都必须显式产生新规则。

### 4. Make quote state a first-class contract

行情状态枚举：

| State | Meaning | Can trigger by default |
|---|---|---|
| `unpriced` | 从未取得真实行情，页面可能只有成本占位 | No |
| `live` | 数据源明确表示交易时段实时行情 | Yes |
| `delayed` | 延迟行情但仍在资产允许年龄内 | Configurable, default yes |
| `close` | 最近交易日收盘价 | Manual refresh only by default |
| `nav` | 最新公布基金净值 | Yes when within fund policy |
| `stale` | 超过资产允许年龄 | No |
| `error` | 本轮获取失败且没有可接受快照 | No |

后端返回 `quote_state`、`source`、`quoted_at`、`fetched_at`、`fresh_until`、`is_actionable` 和稳定 `error_code`。前端不自行推断行情是否可用。

股票/ETF 与开放式基金使用不同新鲜度策略。节假日新鲜度按交易日或公布日策略判断，不用固定自然日简单推导。手动刷新在休市时可以保存收盘价，但必须在响应和 UI 中标记 `close`，并默认不把它伪装为实时行情。

### 5. Isolate providers and the market calendar

定义以下端口：

```python
class QuoteProvider(Protocol):
    def fetch(self, instruments, now) -> list[ProviderQuote]: ...

class MarketCalendar(Protocol):
    def session_status(self, market, now) -> MarketSessionStatus: ...
```

生产适配器使用 akshare；测试适配器使用内存 fixture。fixture 模式禁止导入或调用任何真实行情和日历 API。

生产策略：

- 交易日历按市场和日期缓存，成功结果至少缓存到次日开盘前。
- 外部调用必须有明确连接与总超时，不把异常原文直接返回 UI。
- 同一监控周期内，同一数据集最多下载一次，同一标的最多解析一次。
- 失败使用指数退避和小幅抖动；连续失败进入短期熔断，手动刷新可显式试探。
- 日历失败时只能使用有有效期的最近成功日历或工作日降级，并在周期中标记 `degraded`。
- 提供方原始字段先映射为内部 DTO，再进入领域逻辑，领域层不得依赖 DataFrame 列名。

首轮保留 akshare 单主源，但接口允许以后增加备用源。多源冲突时不能静默择值，必须记录来源优先级和偏差诊断。

### 6. Commit monitoring results atomically and report committed truth

监控周期流程：

```text
create cycle -> resolve market -> load active positions -> fetch/normalize quotes
             -> persist quote snapshots -> evaluate each position
             -> conditional transition + alert/event -> commit
             -> build response from committed rows -> enqueue deliveries
```

关键约束：

- `Position.version` 用于乐观并发控制。
- 触发使用条件更新：只有当前状态和版本仍符合预期时才能变更。
- 告警的业务幂等键为 `position_id + rule_id + trigger_sequence`，而不是依赖可变时间字符串。
- 单个标的失败不能回滚其他标的已验证结果；使用每标的 savepoint 或明确分批事务。
- 发生唯一约束冲突时重新读取已提交事实，不返回本地未提交的 `triggered` 数组。
- 外部通知仅在主事务提交后入队或写入 `DeliveryAttempt`，通知失败不回滚仓位。
- 同一进程内调度器继续 `max_instances=1`；手动刷新与调度刷新通过数据库周期锁或应用级互斥避免重复全市场抓取。

选择乐观并发而不是 SQLite 行锁，因为 SQLite 不提供与服务器数据库相同的行级锁语义，版本条件更新更容易测试和迁移。

### 7. Use explicit accounting formulas

首轮成本匹配采用 FIFO，并把方法保存为账户设置，为未来加权平均预留扩展。

```text
lot_cost = quantity * unit_cost + buy_fees + buy_taxes
close_proceeds = quantity * close_price - sell_fees - sell_taxes
realized_pnl = close_proceeds - allocated_lot_cost
market_value = remaining_quantity * actionable_or_latest_price
unrealized_pnl = market_value - remaining_cost
position_weight = market_value / total_actionable_market_value
stop_risk_amount = max(0, current_price - stop_price) * remaining_quantity
estimated_loss_at_stop = (stop_price - remaining_unit_cost) * remaining_quantity - estimated_exit_cost
```

如果行情为 `unpriced/error/stale`，市场价值可以显示“基于最后可用价的估值”，但不得混入标记为实时的组合指标。API 同时返回 `valuation_coverage_pct`，页面明确展示有多少仓位使用可行动行情。

### 8. Persist bounded history and immutable events

行情历史只保存系统实际取得并用于展示/判断的快照，不尝试补齐全市场 K 线。默认保留 365 天，可配置 30 至 3650 天。

`PositionEvent` 至少覆盖：

- `position_opened`
- `lot_added`
- `rule_activated`
- `quote_applied`
- `stop_triggered`
- `risk_acknowledged`
- `risk_override`
- `partial_close`
- `position_closed`
- `metadata_changed`
- `imported`

事件 payload 使用带 `schema_version` 的 JSON 快照。事件不可更新或删除；用户删除仓位时默认软删除业务对象，审计事件和告警继续保留。物理清理只能通过独立的数据保留操作执行。

趋势图默认按时间窗口下采样，最多返回 1000 点。图表显示价格线、有效止损线、触发点、规则变更和平仓点，不引入装饰性图形。

### 9. Evolve APIs without breaking the current frontend

保留现有路由一个兼容周期，新增以下资源：

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/monitoring/status` | 调度器、最近周期、行情覆盖和提供方状态 |
| GET | `/api/monitoring/cycles` | 分页周期诊断 |
| POST | `/api/monitoring/refresh` | 统一手动刷新，支持可选 instrument/position 范围 |
| GET | `/api/positions` | 搜索、筛选、排序和分页仓位 |
| GET | `/api/positions/{id}` | 完整仓位、批次、规则和估值摘要 |
| POST | `/api/positions/{id}/lots` | 加仓 |
| POST | `/api/positions/{id}/close` | 部分或全部平仓 |
| POST | `/api/positions/{id}/rearm` | 触发后重新布防 |
| GET | `/api/positions/{id}/history` | 图表序列和事件时间线 |
| GET | `/api/alerts` | 增强筛选、排序和分页 |
| POST | `/api/alerts/{id}/acknowledge` | 确认风险，不等同于已读 |
| GET/PUT | `/api/settings/*` | 按 monitoring/history/notifications 分组设置 |
| POST | `/api/imports/holdings/preview` | CSV 校验预览，不写入 |
| POST | `/api/imports/holdings/commit` | 使用预览令牌提交 |
| GET | `/api/exports/positions.csv` | 导出仓位和批次 |

所有列表使用 `{items,total,page,size}`。筛选和排序字段采用白名单；错误使用稳定 `code`、中文 `message`、`correlation_id` 和可选逐行/逐标的 details。

兼容层将新模型映射为现有 `HoldingResponse`。新增 API 稳定后，README 和 OpenAPI 标记旧字段弃用，但首轮不移除。

### 10. Redesign information architecture around risk and trust

主导航保持四个入口，避免增加过多一级页面：

```text
仪表盘 | 持仓 | 告警 | 设置
                 |
           详情内包含历史
```

#### Dashboard

桌面首屏结构：

```text
+------------------------------------------------------------------+
| 监控状态: 交易中 | 最近成功 10:05 | 3/4 新鲜 | 1 个失败 [诊断] |
+------------------------------------------------------------------+
| 风险摘要: 1 个已触发 | 预计止损损失 ¥... | 高风险仓位 ¥...     |
+------------------------------------------------------------------+
| 未实现盈亏 | 活动市值 | 活动成本 | 已实现盈亏 | 行情覆盖率       |
+------------------------------------------------------------------+
| 风险持仓表: 标的 / 权重 / 当前价状态 / 盈亏 / 止损 / 风险金额   |
+------------------------------------------------------------------+
| 今日事件与告警                                                   |
+------------------------------------------------------------------+
```

监控状态条永远可见且紧凑：健康为中性，降级为黄色，停止或数据不可用为红色。它不得与业务风险颜色混为同一含义。

风险摘要优先展示需要行动的事实。没有风险时缩短高度，不使用大面积“安全”色块。资产卡片使用千分位、正负号和等宽数字。

#### Positions list

- 工具栏：搜索、生命周期、资产类型、行情状态、风险等级、排序。
- 桌面表格列：标的、数量/成本、当前价与状态、绝对/百分比盈亏、仓位权重、止损价/距离、预计止损损失、状态、操作。
- 允许用户隐藏非关键列，但必须保留标的、行情状态、止损距离和生命周期。
- 手机端默认紧凑卡片，只显示标的、状态、当前价、盈亏、止损距离和行情状态；展开后显示数量、成本和权重。
- 筛选状态写入 URL query，返回页面后保留上下文。

#### Position detail

- 活动仓位首屏：当前价及可信状态、绝对/百分比盈亏、止损价/距离、预计止损损失。
- 第二层：价格与止损线图、当前规则、行情来源。
- 第三层：交易批次、事件时间线、告警。
- 操作层级：刷新/编辑规则为常规操作；部分/全部平仓为警示操作；删除/清理为危险操作。
- 关闭仓位切换为复盘模式：平仓价、净已实现收益、费用、持有天数、触发到平仓滑点、事件时间线；隐藏刷新和止损编辑。
- 触发仓位显示固定处置条，提供“确认风险”“重新布防”“记录平仓”，不能仅靠红色表达。

#### Alerts

- 默认按未处理优先、时间倒序。
- 支持未读/未处理/已处置、日期、标的和类型筛选。
- 告警行显示触发时规则、当前价、止损价、风险金额、行情状态和处置状态。
- 点击进入告警详情抽屉或仓位详情对应事件锚点。
- “全部已读”不等于“全部已处置”，两个概念在文案和 API 中分离。

#### Settings

设置分为四组：刷新与监控、行情与历史、通知、数据与诊断。继续提供“及时/均衡/省资源”预设，但高级设置展示实际范围、影响和当前运行状态。

Webhook 密钥只允许写入和替换，不回显完整值。系统通知权限由用户按钮触发请求，页面加载时不得自动弹权限框。

### 11. Use a restrained operational visual system

保留现有克制、工作型界面风格，不采用营销式大标题、装饰渐变或卡片套卡片。

颜色语义：

- 品牌/主操作：低饱和绿色，仅用于导航、主按钮和选中状态。
- 中国市场盈亏：红色表示盈利、绿色表示亏损，同时显示正负号和文字。
- 业务危险：红色表示已触发、删除等危险状态，不与“盈利红”只靠颜色区分。
- 监控降级：琥珀色；未知/过期：中性灰；健康：中性深色或轻绿色文字。
- 所有状态必须同时使用图标、文本或结构标识。

统一使用 4/8px 间距体系、最大 8px 常规卡片圆角、稳定表格行高和至少 44px 手机触控目标。价格、金额、百分比使用 tabular numbers，金额默认千分位。

响应式断点：

- `>= 1024px`：完整顶部导航和高密度表格。
- `768-1023px`：保留顶部导航，表格裁剪次要列或转摘要列表。
- `360-767px`：底部主导航、单列内容、紧凑卡片、底部安全区。

固定底部导航不得遮挡最后一项内容；对话框在手机端使用接近全屏的 sheet，提交操作固定在 sheet 底部而不是页面底部。

### 12. Centralize frontend server state and polling

Pinia store 按资源划分：`monitoring`、`positions`、`alerts`、`settings`。页面持有筛选和临时表单状态，服务端数据、最后成功时间、刷新状态和错误放入 store。

轮询策略：

- 应用外壳只轮询轻量监控摘要和未读计数。
- 仪表盘可订阅同一监控摘要，不创建重复计时器。
- 页面隐藏时降低轮询频率；重新可见时立即进行一次轻量刷新。
- 同一资源只允许一个在途请求；新请求可以复用或取消旧请求。
- 后台刷新失败保留最后成功数据，并显示数据年龄。
- 手动刷新使用周期 ID 跟踪进度，避免 60 秒无反馈等待。

首轮不引入大型数据请求框架；先使用 Pinia 和现有 axios 封装实现。如果缓存、取消和失效逻辑显著复杂，再评估 TanStack Query。

### 13. Decouple alert facts from delivery channels

站内 `Alert` 是唯一事实来源。每个外部通道通过 `DeliveryAttempt` 异步投递：

- 系统通知：前端在检测到新告警后使用 Web Notification API；无权限时仍显示站内告警。
- Webhook：后端发送最小可配置 payload，支持签名、超时、幂等键和有限重试。
- 未来邮件/企业微信复用同一通道接口。

默认 payload 不包含数量、成本或总资产；用户可在设置中明确选择“基础信息”或“包含持仓详情”。日志只记录通道、告警 ID、结果和错误类别。

### 14. Make imports previewable and exports stable

CSV 导入采用两阶段流程：上传/解析后返回预览令牌、规范化行和逐行错误；只有用户确认后才事务性提交。预览令牌有短时有效期且只存本机临时目录。

导出文件包含 schema 版本、生成时间和明确列名。金额和数量以不丢精度的文本形式输出。公式型单元格内容必须转义，防止电子表格公式注入。

数据备份继续使用 SQLite 一致性快照和 checksum manifest。面向 UI 的备份入口只能写入受控备份目录，恢复仍要求服务停止并通过命令执行，避免浏览器误操作替换活动数据库。

### 15. Replace ad hoc schema mutation with ordered migrations

采用有序迁移脚本；优先评估 Alembic，因为项目已使用 SQLAlchemy。若不引入 Alembic，内部迁移框架也必须满足相同要求：每个版本独立 `upgrade/downgrade`、不可跳号、事务边界明确、可检测未知版本。

恢复必须验证：checksum、SQLite integrity、manifest 格式、schema version 是否在支持范围、目标路径是否属于配置数据库。替换前创建当前数据库恢复点，替换失败自动还原。

### 16. Preserve local security and privacy defaults

- 服务默认且文档化地只绑定 `127.0.0.1`。
- 不因增加 Webhook 而开放 CORS 或网络监听。
- 所有自由文本有长度限制，URL 仅允许 `https`，本地调试例外必须显式配置。
- Webhook 阻止环回、私网和链接本地地址，除非用户开启本地目标高级选项，避免 SSRF 风险。
- 密钥使用操作系统安全存储；无法使用时至少使用本机权限受限文件，禁止明文回显。
- CSV 限制文件大小、行数和编码；导入错误不得包含完整敏感行。
- 日志保持隐私友好，诊断包必须先展示包含内容并允许排除数据库。

### 17. Bound storage and query cost

- `QuoteSnapshot(instrument_id, quoted_at)`、`PositionEvent(position_id, created_at)`、`MonitoringCycle(started_at)` 建复合索引。
- 历史保留任务分批删除，避免长时间 SQLite 写锁。
- 图表 API 服务端下采样，不向浏览器发送全部原始点。
- 仪表盘使用 SQL 聚合或专用查询，不加载全部历史 ORM 对象。
- 全市场数据集按周期缓存，后台抓取设置硬超时。
- 默认数据库启用 WAL 和合理 busy timeout，并在备份测试中覆盖 WAL 一致性。

### 18. Strengthen testing around observable behavior

测试金字塔：

1. 领域单元测试：Decimal、止损计算、FIFO、状态机、行情策略。
2. 服务集成测试：事务、并发触发、幂等、迁移、恢复、保留任务。
3. Provider 契约测试：固定 DataFrame/JSON fixture，不访问网络。
4. Vue 组件测试：真实挂载页面，验证加载、错误、筛选、表单和响应式状态。
5. 浏览器 E2E：使用隔离数据库和 fixture provider 完成新增、刷新、触发、确认、重新布防、部分平仓和关闭流程。
6. 可选真实行情测试：仅显式运行，结果与必选门禁分开。

必选门禁设置网络阻断或 provider 哨兵，任何真实网络调用立即失败并指出调用点，而不是等待超时。

### 19. AI implementation guardrails

后续 AI 实施必须遵循：

- 按 `tasks.md` 阶段执行，每个阶段完成测试和迁移验证后再进入下一阶段。
- 不一次性替换全部 ORM 模型或前端页面；先建立新接口和兼容适配器。
- 不删除旧字段、旧路由或现有迁移数据，除非任务明确进入兼容清理阶段。
- 不在浏览器中进行财务计算；领域结果由后端返回。
- 不用“当前时间”等不可注入全局值编写领域测试。
- 不把数据源返回的原始异常和字段直接暴露给 API。
- 不把外部投递、图表或导入功能放入止损触发主事务。
- 每次迁移必须在复制的 schema v2 数据库上验证升级、降级和数据保真。
- UI 完成后必须在 390x844、768x1024 和 1440x900 视口检查无横向溢出、固定导航遮挡和文本截断。

## Risks / Trade-offs

- [数据模型迁移范围大] -> 分两阶段创建影子表和兼容读取，先迁移再切换写路径；对代表性旧数据库做校验和前后对账。
- [SQLite 并发写能力有限] -> 保持单调度器，缩短事务，使用 WAL、busy timeout、版本条件更新和每标的 savepoint。
- [免费行情源语义不稳定] -> 适配层、字段契约 fixture、稳定错误码、状态透明和备用源接口；不承诺交易级实时。
- [保存历史导致数据库增长] -> 默认保留期、下采样、索引、分批清理和设置页容量提示。
- [新界面信息过多] -> 风险优先、渐进披露、可隐藏列和移动端紧凑卡片；不把所有字段堆在首屏。
- [盈利红与危险红冲突] -> 盈亏始终带正负号，危险使用图标、标签和结构，不能只靠颜色。
- [外部通知泄露持仓] -> 默认关闭、最小 payload、用户明确选择详情级别、密钥不回显。
- [兼容层长期存在形成负担] -> 明确一个兼容周期，在日志和文档记录旧接口使用，后续单独变更清理。
- [新增依赖增加包体和维护成本] -> Alembic/组件测试工具等依赖逐项评审；图表库必须按需加载并纳入预算。
- [功能范围过大] -> 任务按 P0/P1/P2 切片，每个切片独立可发布；通知、历史 UI、导入导出不得阻塞 P0 可靠性修复。

## Migration Plan

### Phase 0: Baseline and safety net

1. 固化 schema v2 代表性数据库 fixture 和当前 API 快照。
2. 先修复离线冒烟，添加网络哨兵、并发触发回归和关闭持仓展示测试。
3. 增加功能开关 `STOP_LOSS_V2_MODE`，默认关闭新写路径。

### Phase 1: Monitoring trust

1. 引入行情状态 DTO、日历和 provider 接口。
2. 新增 `monitoring_cycles` 和规范化 quote metadata；现有持仓表继续写最新价格。
3. 前端增加监控状态条和行情状态标签。
4. 切换 fixture 到完全离线适配器，完整质量门禁必须通过。

### Phase 2: Domain shadow model

1. 新增 instrument、position、lot、stop_rule、event 和 history 表。
2. 迁移每条现有 holding 为一个 instrument、position、lot 和 active rule；closed holding 生成 close allocation。
3. 运行对账：数量、成本、状态、止损价、告警数量和汇总盈亏必须匹配。
4. 新服务双读比对但旧 API 仍由兼容层输出。

### Phase 3: Switch writes and UI

1. 新增/编辑/刷新/触发/平仓切换到新领域服务。
2. 启用部分平仓、重新布防和事件历史。
3. 发布新版仪表盘、持仓、详情、告警和设置页面。
4. 保留旧 DTO 并运行 API 契约测试。

### Phase 4: Extensions

1. 启用历史图表与保留任务。
2. 启用系统通知和可选 Webhook。
3. 启用 CSV 预览导入、导出和诊断入口。

### Rollback

- 每次迁移前创建 checksum 备份及 manifest。
- Phase 1 可通过功能开关回到旧展示，新增诊断表可保留。
- Phase 2/3 回滚先停止服务，验证旧表在双写期内仍完整，再降级 schema。
- 一旦新模型成为唯一写入源，不允许直接降级；必须先执行反向同步迁移并通过对账。
- 外部通知和导入导出均可独立关闭，不影响核心监控。

## Open Questions

1. 默认成本匹配采用 FIFO 是否符合目标用户习惯，还是需要首轮支持加权平均？
2. 休市时手动刷新取得最近收盘价后，是否允许用户显式选择“用收盘价判断止损”？设计默认不自动触发。
3. 开放式基金净值的新鲜度应按自然日、交易日还是基金公布日历配置？
4. 价格历史默认保留 365 天是否合适，是否需要按资产类型设置不同周期？
5. 第一种外部通知通道优先 Webhook、企业微信还是仅系统通知？
6. 是否需要在首轮暴露“默认账户”概念，还是只在数据库中预留？
7. CSV 导入是否需要兼容某一券商的导出格式，还是只提供项目标准模板？
8. 新 API 稳定后，旧 `/api/holdings` 兼容周期按版本还是按发布日期结束？
9. 图表是否接受一个轻量依赖，还是先用原生 Canvas；必须在实现前比较包体、可访问性和维护成本。
10. 未来高级止损策略的首选顺序建议为保本止损、ATR/吊灯止损、时间止损、分级减仓，需要另建变更而不是加入本变更。
