## Context

这是一个全新的项目，从零开始构建一个"只止损不止盈"的持仓管理工具。没有现有代码需要兼容，没有遗留系统约束。

## Goals / Non-Goals

**Goals:**
- 提供持仓 CRUD，支持 A 股和基金（场内 ETF + 场外基金）
- 实现三种止损模式：固定价格、百分比、移动（trailing）止损
- 交易日自动拉取实时价格，触达止损时自动生成告警
- 前端仪表盘展示资产全貌和止损状态
- 浏览器内弹窗告警通知

**Non-Goals:**
- 不接入券商交易 API，不自动下单
- 不支持止盈设置（核心理念约束）
- 不接入港股/美股（初期范围）
- 不实现多用户/登录系统（单用户单机）

## Decisions

### 1. 后端：FastAPI + SQLite + SQLAlchemy

**选择理由：**
- FastAPI：异步原生支持，自动 OpenAPI 文档，类型校验（Pydantic），适合前后端分离
- SQLite：零配置，单文件部署，单用户场景完全够用。换成 PostgreSQL 只需改连接串
- SQLAlchemy：成熟的 ORM，用其声明式模型定义，后续如需换数据库几乎无需改代码

**Alternatives considered:**
- Flask：更轻量但不原生支持异步，缺少自动校验和文档生成
- 纯 SQL：更直接但缺少 ORM 的类型安全和迁移工具

### 2. 前端：Vue 3 (Composition API) + Vite + Element Plus

**选择理由：**
- Vue 3：中文社区活跃，Element Plus 组件库成熟美观，适合数据展示型界面
- Vite：极快的开发体验
- Element Plus：表格、表单、通知弹窗、弹窗组件开箱即用

**Alternatives considered:**
- React + Ant Design：同样优秀，但 Vue 生态在国内金融类应用中更常见

### 3. 行情数据：akshare

**选择理由：**
- pip install 即用，无需 API Key
- 覆盖 A 股实时行情和基金净值
- 自带交易日历数据

**风险点：** 爬虫源，偶尔可能不稳定。应对：本地缓存最新价，接口失败时降级使用缓存价。

### 4. 定时任务：APScheduler

**选择理由：**
- 进程内调度，不需要额外部署 Celery/Redis
- 支持 Cron 表达式和间隔触发器
- 单用户场景足够

**配置：** 交易日 9:30-15:00，每 5 分钟执行一次。可通过设置页面调整。

### 5. 前后端通信

- REST API，JSON 格式
- 前端通过轮询（polling）获取最新数据，默认 30 秒间隔
- 不做 WebSocket，减少复杂度。30 秒延迟在非高频场景下可接受

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Vue 3 SPA (Vite)                         │
│  ┌──────────┬──────────┬──────────┬──────────┐              │
│  │Dashboard │ Holdings │  Alerts  │ Settings │              │
│  │          │   CRUD   │   List   │          │              │
│  └──────────┴──────────┴──────────┴──────────┘              │
│         │          │          │        │                     │
│         └──────────┴──────────┴────────┘                     │
│                       │ axios polling                        │
├───────────────────────┼──────────────────────────────────────┤
│                 FastAPI REST API                             │
│  ┌──────────┬──────────┬──────────┬──────────┐              │
│  │/holdings │ /prices  │ /alerts  │/dashboard│              │
│  └──────────┴──────────┴──────────┴──────────┘              │
│         │          │                              │          │
├─────────┼──────────┼──────────────────────────────┼──────────┤
│         │    ┌─────┴──────┐                        │          │
│         │    │ APScheduler │                        │          │
│         │    │  price job  │                        │          │
│         │    └─────┬──────┘                        │          │
│         │          │ akshare                        │          │
│         │    ┌─────┴──────┐                        │          │
│         │    │  StopLoss   │                        │          │
│         │    │   Engine    │                        │          │
│         │    └─────┬──────┘                        │          │
│         │          │                                │          │
│  ┌──────┴──────────┴────────────────────────────────┴────┐    │
│  │                SQLAlchemy ORM                          │    │
│  │                   SQLite                                │    │
│  └───────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

## Data Model

```
holdings
├── id: INTEGER PK
├── code: VARCHAR(20)          -- 股票/基金代码
├── name: VARCHAR(100)         -- 名称
├── type: VARCHAR(10)          -- "stock" | "fund"
├── buy_price: DECIMAL(10,4)   -- 买入价
├── quantity: INTEGER          -- 数量（股/份）
├── buy_date: DATE             -- 买入日期
├── current_price: DECIMAL(10,4)-- 最新价格（缓存，定时刷新）
├── highest_price: DECIMAL(10,4)-- 历史最高价（trailing stop用）
├── stop_loss_method: VARCHAR(20)-- "fixed"|"percentage"|"trailing"
├── stop_loss_value: DECIMAL(10,4)-- 止损参数值
├── stop_loss_price: DECIMAL(10,4)-- 计算后的止损价（冗余，方便展示）
├── status: VARCHAR(20)        -- "holding" | "stopped_out"
├── close_price: DECIMAL(10,4) -- 平仓价（手动平仓时记录）
├── created_at: DATETIME
└── updated_at: DATETIME

alerts
├── id: INTEGER PK
├── holding_id: INTEGER FK → holdings.id
├── trigger_price: DECIMAL(10,4) -- 触发时的止损价
├── current_price: DECIMAL(10,4) -- 触发时的当前价
├── read: BOOLEAN DEFAULT FALSE
└── created_at: DATETIME
```

## API Routes

| Method | Path                    | Description          |
|--------|-------------------------|----------------------|
| POST   | /api/holdings           | 新建持仓              |
| GET    | /api/holdings           | 持仓列表（含计算字段）|
| GET    | /api/holdings/{id}      | 持仓详情              |
| PUT    | /api/holdings/{id}      | 更新止损参数          |
| DELETE | /api/holdings/{id}      | 删除持仓              |
| POST   | /api/holdings/{id}/close| 手动平仓              |
| GET    | /api/prices             | 获取所有持仓最新价格   |
| POST   | /api/prices/refresh     | 手动触发价格刷新       |
| GET    | /api/alerts             | 告警列表              |
| GET    | /api/alerts/count       | 未读告警数            |
| PUT    | /api/alerts/{id}/read   | 标记已读              |
| PUT    | /api/alerts/read-all    | 全部标记已读           |
| GET    | /api/dashboard          | 仪表盘数据            |
| GET    | /api/settings           | 获取设置              |
| PUT    | /api/settings           | 更新设置              |

## Project Structure

```
stop-loss-only/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── database.py          # SQLAlchemy engine/session
│   ├── models.py            # ORM 模型
│   ├── schemas.py           # Pydantic 请求/响应模型
│   ├── routers/
│   │   ├── holdings.py
│   │   ├── prices.py
│   │   ├── alerts.py
│   │   └── dashboard.py
│   ├── services/
│   │   ├── stop_loss.py     # 止损计算引擎
│   │   └── price_fetcher.py # akshare 价格拉取
│   ├── scheduler.py         # APScheduler 定时任务
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── Dashboard.vue
│   │   │   ├── Holdings.vue
│   │   │   ├── HoldingDetail.vue
│   │   │   ├── Alerts.vue
│   │   │   └── Settings.vue
│   │   ├── components/
│   │   │   ├── HoldingForm.vue
│   │   │   ├── PortfolioSummary.vue
│   │   │   ├── HoldingsTable.vue
│   │   │   └── AlertBadge.vue
│   │   ├── api/             # axios 封装
│   │   ├── router/
│   │   └── App.vue
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
└── openspec/
```

## Risks / Trade-offs

- **akshare 数据源不稳定** → 降级策略：API 失败时使用数据库缓存的 current_price，前端显示"数据延迟"标记
- **trailing stop 在涨停/跌停时失效** → 涨停无法买入是市场限制，不在系统职责内；跌停时大概率已触发止损，无需额外处理
- **SQLite 并发写入限制** → 单用户场景不会遇到锁竞争问题
- **场外基金净值 T 日延迟** → 前端明确标注净值日期，与实时价格区分显示
