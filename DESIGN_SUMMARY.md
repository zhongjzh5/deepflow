# 设计思路摘要（FastAPI + Vue 前后端分离）

## 目标

- 后端使用 **FastAPI** 提供 HTTP API
- 前端使用 **Vue 3 + Vite** 提供 Web UI
- 前后端分离开发与部署，代码分在两个独立目录：`backend/` 与 `frontend/`
- 开发阶段支持联调：前端通过 Vite dev proxy 访问后端接口

## 总体结构

```
D:\deepflow
├─ backend\
│  ├─ main.py
│  ├─ requirements.txt
│  ├─ README.md
│  └─ .gitignore
├─ frontend\
│  ├─ package.json
│  ├─ vite.config.js
│  ├─ index.html
│  ├─ README.md
│  ├─ .gitignore
│  └─ src\
│     ├─ main.js
│     └─ App.vue
└─ README.md
```

## 后端设计（FastAPI）

### 关键点

- **入口文件**：`backend/main.py` 暴露 `app` 给 Uvicorn 启动
- **跨域策略（CORS）**：允许前端开发地址访问（`http://localhost:5173` / `http://127.0.0.1:5173`）
- **接口分层**：当前示例直接在 `main.py` 提供 API；后续可拆分为 `routers/`, `services/`, `schemas/` 等

### 当前示例接口

- `GET /health`：健康检查
- `GET /api/hello?name=...`：示例业务接口，返回 JSON

### 后端依赖与安装

- 依赖文件：`backend/requirements.txt`
- 主要依赖：
  - `fastapi`
  - `uvicorn[standard]`

### 后端运行步骤（Windows / PowerShell）

在 `D:\deepflow\backend` 下执行：

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

访问：

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/api/hello?name=deepflow`

## 前端设计（Vue + Vite）

### 关键点

- **构建工具**：Vite
- **入口文件**：`frontend/src/main.js` 挂载 `App.vue`
- **联调方式**：
  - 前端代码请求 `/api/...`
  - Vite dev server 通过 `vite.config.js` 的 `server.proxy` 将 `/api` 与 `/health` 转发到后端 `http://127.0.0.1:8000`
  - 好处是前端开发时不需要手写后端完整 URL，也避免了大多数 CORS 场景下的复杂度

### 前端依赖与安装

- 依赖文件：`frontend/package.json`
- 安装命令（必须在 `frontend/` 目录执行）：

```powershell
npm install
```

### 前端运行步骤

在 `D:\deepflow\frontend` 下执行：

```powershell
npm run dev
```

打开：

- `http://localhost:5173`

页面里点击按钮会调用：

- `GET /api/hello?name=...`（通过 dev proxy 转发到后端）

## 配置步骤摘要（从零到可联调）

### 1. 创建目录

- 创建根目录 `deepflow`
- 在根目录下创建：
  - `backend/`
  - `frontend/`

### 2. 后端配置

- 添加 `backend/requirements.txt`
- 添加 `backend/main.py`：
  - 创建 `FastAPI()` 实例
  - 配置 `CORSMiddleware`
  - 提供 `/health` 与 `/api/hello` 示例

### 3. 前端配置

- 添加 `frontend/package.json`（Vue + Vite）
- 添加 `frontend/vite.config.js`：
  - 配置 `server.port = 5173`
  - 配置 `server.proxy`：将 `/api` 与 `/health` 指向后端 `127.0.0.1:8000`
- 添加 `frontend/src/App.vue`：
  - 使用 `fetch('/api/hello?...')` 调用后端

## 常见问题

### npm 报 ENOENT 找不到 package.json

原因：在 `D:\deepflow` 根目录执行了 `npm install`，但 `package.json` 位于 `D:\deepflow\frontend`。

解决：进入 `frontend` 再执行：

```powershell
cd D:\deepflow\frontend
npm install
```

## 后续可扩展方向

- 后端：引入 `pydantic` schema 分层、`APIRouter` 路由拆分、数据库与迁移（如 SQLAlchemy + Alembic）
- 前端：引入路由（Vue Router）、状态管理（Pinia）、UI 组件库等
- 工程化：根目录增加统一启动脚本（例如在根目录加一个 `package.json` 转发前端命令），或使用 `docker-compose` 一键启动

## 记录

### 2026-02-05 15:37 (UTC+08:00)

- 项目按“全部重来”方式重新初始化为前后端分离结构：根目录下 `backend/`（FastAPI）与 `frontend/`（Vue + Vite）。
- 排查并确认 `npm ENOENT` 原因：在 `D:\deepflow` 根目录执行 `npm install` 导致找不到 `package.json`；正确做法是在 `D:\deepflow\frontend` 下执行 `npm install`。
- 新增聊天占位接口：后端 `POST /api/chat`，请求体 `{"message": "..."}`，响应 `{"reply": "..."}`；当前返回 mock 回复，后续可替换为真实大模型调用逻辑。
- 前端替换为 AI 聊天窗口：消息列表（区分你/模型）、输入框、发送按钮、loading 状态与自动滚动；通过 Vite dev proxy 调用 `/api/chat` 与后端联调。
