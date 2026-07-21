## 1. 后端项目初始化

- [x] 1.1 创建 backend/ 目录，初始化 FastAPI 项目骨架（main.py, requirements.txt）
- [x] 1.2 配置 SQLAlchemy + SQLite，创建 database.py（engine + session factory）
- [x] 1.3 定义 ORM 模型 models.py（holdings 表 + alerts 表）
- [x] 1.4 定义 Pydantic schemas.py（请求/响应模型）
- [x] 1.5 配置 CORS 中间件，允许前端跨域访问

## 2. 前端项目初始化

- [x] 2.1 使用 Vite 创建 Vue 3 项目，安装 Element Plus、axios、vue-router、pinia
- [x] 2.2 配置 vite.config.js（开发代理到 FastAPI :8000）
- [x] 2.3 创建路由结构（Dashboard, Holdings, Alerts, Settings）
- [x] 2.4 封装 axios 实例（baseURL, 错误拦截）

## 3. 止损引擎

- [x] 3.1 实现 StopLossEngine 类，支持三种止损模式的计算方法
- [x] 3.2 实现 fixed 止损：stop_loss_price = stop_loss_value
- [x] 3.3 实现 percentage 止损：stop_loss_price = buy_price × (1 - value/100)
- [x] 3.4 实现 trailing 止损：stop_loss_price = highest_price × (1 - value/100)，止损价永不下降
- [x] 3.5 实现 trigger 判定：current_price ≤ stop_loss_price → 触发
- [x] 3.6 编写止损引擎单元测试，覆盖三种模式及边界情况

## 4. 价格拉取服务

- [x] 4.1 集成 akshare，实现 A 股实时价格获取函数
- [x] 4.2 实现基金净值获取函数（ETF 实时 + 场外净值）
- [x] 4.3 实现批量价格获取，单次调用拉取所有持仓价格
- [x] 4.4 实现交易日检测（使用 akshare 交易日历）
- [x] 4.5 实现错误降级：API 失败时保留数据库缓存价，返回状态标记

## 5. 后端 API 路由

- [x] 5.1 实现 POST /api/holdings — 创建持仓（含参数校验）
- [x] 5.2 实现 GET /api/holdings — 持仓列表（含计算字段：止损价、盈亏%、止损距离%）
- [x] 5.3 实现 GET /api/holdings/{id} — 持仓详情
- [x] 5.4 实现 PUT /api/holdings/{id} — 更新止损参数（已止损的不可修改）
- [x] 5.5 实现 DELETE /api/holdings/{id} — 删除持仓
- [x] 5.6 实现 POST /api/holdings/{id}/close — 手动平仓
- [x] 5.7 实现 GET /api/prices — 获取所有持仓最新价格
- [x] 5.8 实现 POST /api/prices/refresh — 手动触发价格刷新 + 止损检查
- [x] 5.9 实现 GET/PUT /api/alerts — 告警列表、标记已读、全部已读
- [x] 5.10 实现 GET /api/alerts/count — 未读告警数
- [x] 5.11 实现 GET /api/dashboard — 仪表盘聚合数据（总资产、盈亏、今日告警）

## 6. 定时任务

- [x] 6.1 配置 APScheduler，在 FastAPI startup 事件中启动
- [x] 6.2 实现价格监控 job：拉取价格 → 更新 highest_price → 检查止损触发 → 生成告警
- [x] 6.3 实现交易日历集成，非交易日跳过执行
- [x] 6.4 实现轮询间隔可配置（默认 5 分钟），通过 Settings API 调整

## 7. 前端页面

- [x] 7.1 实现 Dashboard 页面（总资产卡片 + 持仓盈亏列表 + 今日告警概要）
- [x] 7.2 实现 Holdings 列表页（表格：代码|名称|买入价|当前价|止损价|盈亏%|止损距离%|状态）
- [x] 7.3 实现新建持仓表单（HoldingForm 组件，三种止损模式动态切换字段）
- [x] 7.4 实现持仓详情/编辑页（修改止损参数、手动平仓）
- [x] 7.5 实现 Alerts 告警历史页（未读高亮，支持标记已读）
- [x] 7.6 实现 Settings 设置页（轮询间隔配置）
- [x] 7.7 实现全局 AlertBadge 组件（顶部导航栏未读告警数 + 弹窗通知）
- [x] 7.8 实现前端轮询逻辑（Dashboard 30 秒，告警数 10 秒）

## 8. 集成与收尾

- [x] 8.1 前后端联调，确保所有 API 调用正常工作
- [x] 8.2 添加全局错误处理和加载状态
- [x] 8.3 实现后端设置持久化（settings 表，轮询间隔等配置）
- [x] 8.4 编写 README 启动指南（前后端启动命令、依赖安装）
