# 止损不止盈

一个帮助记录 A 股和基金持仓的投资管理工具。

**核心理念：只止损，不止盈。让利润奔跑，让亏损止步。**

## 技术栈

- 后端：Python FastAPI + SQLAlchemy + SQLite
- 前端：Vue 3 + Element Plus + Vite
- 行情数据：akshare
- 定时任务：APScheduler

## 快速启动（推荐）

项目根目录下提供了一键启停脚本，首次运行会自动安装缺失的依赖。

```powershell
# 启动（默认端口：后端 8001，前端 5173）
.\start.ps1

# 自定义端口
.\start.ps1 -BackendPort 9001 -FrontendPort 3000

# 重启（先关闭旧进程再启动）
.\start.ps1 -Restart

# 停止
.\stop.ps1
```

启动后：
- 前端: http://localhost:5173
- 后端: http://localhost:8001
- API 文档: http://localhost:8001/docs

## 手动启动

也可以分别手动启动前后端。

### 1. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 启动后端

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

API 文档自动生成：http://localhost:8001/docs

### 3. 安装前端依赖

```bash
cd frontend
npm install
```

### 4. 启动前端

```bash
cd frontend
npm run dev
```

浏览器打开：http://localhost:5173

## 止损方式

| 方式       | 说明                           | 示例                       |
|-----------|-------------------------------|---------------------------|
| 固定价格   | 设定一个明确的止损价格           | 买入¥10，止损¥9 → 跌到¥9触发 |
| 百分比     | 从买入价下跌X%止损              | 买入¥10，止损10% → 跌到¥9触发 |
| 移动止损   | 从最高点回落X%止损，止损线只升不降 | 买入¥10，涨到¥18，回落10% → ¥16.20触发 |

## 项目结构

```
stop-loss-only/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── database.py          # 数据库连接
│   ├── models.py            # ORM 模型
│   ├── schemas.py           # Pydantic 模型
│   ├── scheduler.py         # 定时监控任务
│   ├── routers/             # API 路由
│   ├── services/            # 止损引擎 + 价格拉取
│   └── tests/               # 单元测试
├── frontend/
│   ├── src/
│   │   ├── views/           # 页面组件
│   │   ├── components/      # 公共组件
│   │   ├── api/             # axios 封装
│   │   ├── router/          # 路由配置
│   │   └── stores/          # Pinia 状态管理
│   └── vite.config.js
└── openspec/                # 设计文档
```
