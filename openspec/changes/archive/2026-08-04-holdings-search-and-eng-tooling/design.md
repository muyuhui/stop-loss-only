# Design — Holdings 搜索筛选与工程工具链优化

## Context

- 持仓列表 `GET /api/holdings`（`backend/routers/holdings.py::list_holdings`）目前只支持 `status`、`page`、`size`，固定按 `created_at DESC, id DESC` 排序；前端 `Holdings.vue` 无任何搜索/筛选控件。
- 仓库存在孤儿组件 `frontend/src/components/FilterToolbar.vue`（零引用）：为已废弃的 Position 世界设计（lifecycle 开放/关闭、risk normal/triggered/acknowledged 选项），但组件形态（`query` prop + `update:query`/`reset` 事件、响应式网格、总数展示）与 legacy 需求吻合，值得改造而非新建。
- `Holding.stop_loss_price` 是持久化列，由 create/update/rearm 原子维护；`current_price` 也是行内列，监控周期就地更新。因此"止损距离"可在 SQL 层用列计算，无需 join 行情表。
- `presentation.py::holding_payload` 防御性地用 `StopLossEngine.calculate` 重算展示止损价（防列漂移），该展示口径是 UI 真相。
- 工程地雷：README「v4 回滚」runbook 过期（`LATEST_SCHEMA_VERSION=8`）；无 `requires-python`/`.python-version`；`setup.ps1` 只装依赖，不校验 Python 版本也不检查 openspec CLI，而 `verify.ps1` 第 9 步 `openspec validate` 依赖它。
- 约束：本 change 不引入 schema 变更/迁移；遵循既有错误约定（非法枚举参数返回 422，如 `status` 的 `pattern` 校验）；测试必须离线（网络哨兵）；前端遵循 Alerts.vue 的查询/DataState 模式。

## Goals / Non-Goals

**Goals:**
- 持仓列表支持搜索（名称/代码）、状态筛选、类型筛选（A股/基金）、三种排序（最新/名称/风险），全部服务端生效并与分页正确组合。
- 前端持仓页获得可用、响应式的工具栏，排序偏好跨会话记忆。
- 扫除三个工程地雷：README 回滚 runbook 更新、Python 版本锁定+预检、openspec CLI 预检。
- 全程保持向后兼容：无参数请求行为与响应结构不变。

**Non-Goals:**
- 不引入模糊/拼音搜索、URL 状态同步、列可见性配置或多列排序。
- 不删除其他孤儿（如 `PositionDetail.vue`）、不复活 Position/CSV/Webhook 能力、不新增 DB 迁移。
- 不引入 pyproject/uv/poetry 等新打包机制（Python 版本锁定用 `.python-version` + setup 预检实现）。
- 搜索/筛选条件不持久化（只有排序记忆）。

## Decisions

### D1: `search` 参数语义 — 名称/代码子串匹配，SQLite LIKE 转义
- `search` 对 `Holding.name` 与 `Holding.code` 做包含匹配（OR），复用 `routers/alerts.py` 已有的 `contains(autoescape=True)` 模式（转义 `%`/`_`/`\`，配合 `ESCAPE` 子句）。
- 空白/空字符串视为未提供筛选；SQLite LIKE 对 ASCII 不区分大小写（代码/名称场景足够），中文为精确子串。
- 备选：Python 端 `in_` 过滤——被拒：无法与 SQL 分页组合。
- 规模论证：单用户本地工具、持仓量数百级别，LIKE 全表扫描可接受，不为该参数加索引（`code` 已有索引，但 OR 查询下 SQLite 通常仍扫描；不优化）。

### D2: `sort` 参数 — `newest`（默认）/`name`/`risk`，`risk` 用 SQL 距离表达式
- `newest`：`created_at DESC, id DESC`（现状，保持不变）。
- `name`：`name ASC, id ASC`（中文按 SQLite 字节序，不做 locale 排序——备选 py排序被拒，分页一致性优先）。
- `risk`：`CASE WHEN current_price > 0 THEN (current_price - stop_loss_price) / current_price END ASC NULLS LAST, id ASC`。距离最小（最紧迫，含已触发负距离）在前，无估值行情（`current_price = 0` 默认值 → NULL）在最后，与 dashboard 规范"未知距离排在已知之后"一致；`id` 保证稳定分页。
- 使用持久化列 `stop_loss_price`（create/update/rearm 均原子维护）而非在 SQL 中重放 `StopLossEngine.calculate` 公式——避免业务公式双份实现。展示口径仍是 `holding_payload` 的重算值；契约测试断言 SQL 排序顺序与展示距离一致，防列漂移影响排序语义。
- 非法值：`sort` 用 `pattern="^(newest|name|risk)$"` 校验 → 422（与 `status` 同款）。
- 备选：Python 端取全量→算距离→排序→切片——被拒：把分页从 SQL 移到应用层，改动面大、与现有 `count()`+`offset/limit` 模式冲突；仅在列漂移被测试证实为真实问题时作为兜底方案。

### D3: 组合语义 — 先筛选后排序后分页
- 顺序：`status` / `type` / `search` 过滤 → `sort` 排序 → `count()`（过滤后总数）→ `offset/limit` 切片。
- `type` 参数：`pattern="^(stock|fund)$"` 等值过滤（`Holding.type` 列），非法 422。
- 所有参数缺省时行为与响应结构与现状逐字节一致（兼容旧客户端）。

### D4: 前端 — 改造孤儿 `FilterToolbar.vue` 为 `HoldingsToolbar.vue`
- git 重命名 + 语义重写：选项改为 legacy 世界——搜索输入（名称或代码）、状态下拉（全部/持有中/已触发/已关闭）、类型下拉（全部/A股/基金）、排序下拉（最新优先/名称/风险优先）、重置、总数。
- 保留组件原形态（`query` + `update:query` + `reset` 事件、`update()` 内重置 `page: 1`、≤767px 双列网格），`Holdings.vue` 按 Alerts.vue 模式持有 `query` ref 并驱动 `api.get('/holdings', { params: query })`。
- 备选：原位复用（选项语义是 Position 世界的，会误导用户）——被拒；内联在 Holdings.vue（职责混合）——被拒。
- 空搜索词不发 `search` 参数（避免空串查询噪音）。

### D5: 排序偏好记忆 — localStorage
- 键 `holdings.sort`，仅存合法枚举；恢复时校验，非法/缺失回退 `newest`（防御旧值）。先例：通知偏好已用 localStorage。
- 搜索词/筛选不持久化（会话性意图）。

### D6: Python 版本锁定与预检
- 新增根目录 `.python-version` 内容 `3.12`（pyenv 约定，兼作文档）。
- `setup.ps1` 开头增加预检：解析 `python --version`（如 `Python 3.12.4`），major.minor < 3.12 时以中文错误信息退出（提示安装 3.12+ 或使用 pyenv/uv 等）。`start.ps1`/`dev.ps1`/`verify.ps1` 不改（保持最小改动；setup 是入口）。
- README「安装」节补充环境要求：Python ≥ 3.12、Node ≥ 20.19（npm ≥ 7）、openspec CLI（仅验证门禁需要）。

### D7: openspec CLI 预检
- `setup.ps1` 开头 `Get-Command openspec` 检查，缺失时打印中文指引（安装方法以官方文档为准，由实现者确认后写入）并以非零码退出。
- 备选：在 `verify.ps1` 开头预检——保留 verify 的失败信息但另加 setup 早期检查，双保险且成本为零；实现为 setup 预检 + verify.ps1 现有报错文案保留。

### D8: README 回滚 runbook 更新
- 删除过期的「v4 回滚」节，替换为面向当前版本的「回滚」节：先 `stop.ps1` → `backup.ps1` 备份 → `cd backend && python db_admin.py status`（确认当前版本）→ `python db_admin.py downgrade`（非破坏性：新列/索引/表保留，旧代码忽略）→ 重启；数据恢复路径仍指向 `restore.ps1`。
- 该节同时提及"迁移前自动备份"与 `LATEST_SCHEMA_VERSION` 以当前代码为准。

### D9: 测试策略
- 后端：在 `backend/tests/test_api.py`（或新增 `test_holdings_list.py` 沿用既有内存库 bootstrap 模式）覆盖：search 命中/未命中/转义（`%`、`_` 字面量）、search+status+type 组合、sort=newest/name/risk 顺序（含 unpriced 排最后、已触发负距离排最前）、非法 sort/type → 422、total 为过滤后数量、默认参数下与现状等价。
- 前端：`node:test` 纯逻辑（若提取 `query` 构建/校验小工具）；mount spec 用 `vi.mock('../src/api')` 断言：输入触发带 `page: 1` 的新查询、排序选择写入 localStorage、恢复时校验非法值。
- E2E：在 `supported-runtime.spec.js` 增加场景：seed 3 笔不同名称/类型/价格的持仓 → 搜索收窄列表与总数 → risk 排序首项为最近止损 → mobile 视口下工具栏可用无横向滚动。

## Risks / Trade-offs

- [SQLite LIKE 转义易错] → 复用 alerts.py 既有 `contains(autoescape=True)` 实现 + 显式转义契约测试（`%`/`_` 字面量）。
- [`risk` 排序与展示距离可能因列漂移不一致] → 契约测试断言排序首尾与 `holding_payload` 距离一致；若漂移被证实，fallback 为 Python 全量排序（D2 已评估）。
- [localStorage 旧值/脏值] → 恢复时枚举校验，非法回退默认值。
- [E2E 排序断言依赖 fixture 价格（8.8）] → 场景内用确定性 seed（`STOP_LOSS_FIXTURE_PRICE`）并只断言相对顺序而非绝对值。
- [Python 版本解析失败（如 `py` launcher 输出差异）] → 预检解析失败时按"版本不满足"处理并给出明确错误，不静默通过。
- [README runbook 再过期] → 文案改为引用 `db_admin.py status` 输出而非硬编码版本号。

## Migration Plan

- 无数据库迁移。API 参数为纯增量（缺省行为不变），前端与后端同仓发布（SPA 随构建一起部署）。
- 回滚：还原代码即可；localStorage 键 `holdings.sort` 在旧前端下被忽略（无副作用）。

## Open Questions

- 无阻塞性问题。实现时确认 openspec CLI 官方安装方式以写入 setup.ps1 指引文案。
