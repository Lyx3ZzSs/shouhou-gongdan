# 售后工单审核工作台

> **AI 售后智能服务一体化平台** 的子项目 — 负责 AI 生成工单的人工审核与修正回流。

## 项目背景

新能源行业售后服务渠道碎片化（400 电话、企业微信、邮件、小程序），业务复杂度高（算法、气象、考核规则），跨部门协同频繁，工单量已超出人工处理能力。

"AI 售后智能服务一体化平台"通过 AI 自动生成受理单 + 人工审核确认的协作模式，提升工单处理效率与质量。**本项目为其中的人工审核工作台部分**，核心职责是：

- 提供三栏式专业审核界面，供客服坐席逐字段审核 AI 生成的工单
- 将人工修正数据通过 Bad Case 回流机制反哺 AI 模型，形成持续优化闭环

## 功能概览

### 工单审核工作台（前端）

三栏式专业审核界面，支持客服人员高效审核 AI 生成的工单：

| 区域 | 功能 |
|------|------|
| **左侧队列** | 待审核工单列表，支持筛选、排序、SLA 时效倒计时 |
| **中间工作区** | 24 个字段分 8 组展示，diff 对比视图，行内编辑，逐字段确认 |
| **右侧控制台** | 审核进度、当前变更、备注记录 |

**交互特性：**
- 键盘快捷键全程操作（J/K 导航、Cmd+Enter 提交、Cmd+S 暂存等）
- 字段级异常高亮（阻断/告警/建议），一键跳转定位
- Diff 对比视图（原值 → 现值），hover 显示操作按钮
- 密度模式切换（标准/紧凑），响应式布局适配小屏
- 分布式编辑锁防并发冲突，版本冲突检测与提醒
- 自动暂存草稿，切换工单未保存提醒

### 审核后端服务

- **工单审核** — 确认/驳回双分支，乐观锁版本控制，幂等防重
- **字段级审计日志** — 记录每次字段变更的修改人、修改原因、前后值
- **Bad Case 回流** — 人工修正的字段自动入库，用于 AI 模型持续训练
- **分布式编辑锁** — Redis 原子操作，5 分钟 TTL 自动释放，心跳续期
- **JWT 认证与角色鉴权** — 客服专员角色限制

## 技术栈

| 层 | 技术 |
|----|------|
| **后端框架** | Python 3 + FastAPI |
| **ORM** | SQLAlchemy 2.0 (async) |
| **数据库** | PostgreSQL 16 (开发/生产统一) |
| **缓存** | Redis 7+ (分布式锁) |
| **前端框架** | React 18 + TypeScript 5 |
| **构建工具** | Vite 5 |
| **样式方案** | Tailwind CSS 3.4 + shadcn/ui 组件 |
| **状态管理** | Zustand 5 |
| **UI 原语** | Radix UI (无障碍组件) |
| **测试** | pytest (后端) + Vitest (前端) |

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- Docker Compose（用于启动 PostgreSQL + Redis）

### 后端

```bash
# 1. 启动基础设施（PostgreSQL + Redis）
docker compose up -d

# 2. 初始化 Python 环境
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. 初始化数据库表结构
#    首次运行：alembic stamp head（docker compose 已通过 schema_init.sql 创建表）
#    后续增量迁移：alembic upgrade head
alembic stamp head

# 4. 启动服务 (端口 8093)
python -m app.main
# 或: uvicorn app.main:app --reload --port 8093
```

### 前端

```bash
cd frontend
npm install

# 启动开发服务器 (端口 5193)
npm run dev
```

Vite 自动将 `/api` 代理到 `http://localhost:8093`。

### 生成 API 类型

```bash
# 后端生成 OpenAPI spec
cd backend && python scripts/generate_openapi.py

# 前端生成 TypeScript 类型
cd ../frontend && npm run generate-types
```

### 运行测试

```bash
# 后端
cd backend && pytest

# 前端
cd frontend && npx vitest run

# TypeScript 类型检查
cd frontend && npm run typecheck
```

## 项目结构

```
├── backend/
│   ├── app/
│   │   ├── auth/             # JWT 认证与角色鉴权
│   │   ├── core/             # 配置、数据库连接
│   │   ├── models/           # SQLAlchemy ORM 模型
│   │   ├── routers/          # FastAPI 路由 (review, lock)
│   │   ├── schemas/          # Pydantic 请求/响应模型
│   │   └── services/         # 业务逻辑 (审核、锁、审计、Bad Case)
│   ├── tests/                # pytest 测试套件
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── workbench/        # 审核工作台 (新)
│   │   │   ├── components/   # UI 组件
│   │   │   │   ├── queue/    # 左侧队列面板
│   │   │   │   ├── workspace/# 中间审核工作区
│   │   │   │   ├── sidebar/  # 右侧控制台
│   │   │   │   └── primitives/# 基础 UI 组件
│   │   │   ├── hooks/        # 自定义 Hooks
│   │   │   ├── store/        # Zustand 状态管理
│   │   │   ├── lib/          # 工具函数、常量
│   │   │   ├── mock/         # Mock 数据
│   │   │   └── types.ts      # 类型定义
│   │   ├── pages/            # 旧版页面 (保留)
│   │   ├── api/              # API 客户端
│   │   ├── components/       # shadcn/ui 基础组件
│   │   └── lib/              # 通用工具
│   ├── tests/                # Vitest 测试
│   └── package.json
└── docs/                     # 项目文档
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/workorders` | 工单列表（前 50 条） |
| `GET` | `/api/workorders/{id}` | 工单详情 |
| `POST` | `/api/workorders/{id}/review` | 提交审核（确认/驳回） |
| `GET` | `/api/workorders/{id}/audit-logs` | 审核日志 |
| `POST` | `/api/workorders/{id}/lock` | 获取编辑锁 |
| `DELETE` | `/api/workorders/{id}/lock` | 释放编辑锁 |
| `PUT` | `/api/workorders/{id}/lock` | 锁心跳续期 |

## 架构决策

- **三栏布局** — 队列 → 审核区 → 控制台，适配复杂工单的字段级审核需求
- **乐观锁** — 版本号防并发提交，冲突时提示用户刷新
- **锁 release 始终在 finally 中执行** — 防止孤儿锁阻塞队列
- **三层数据管线** — `API 获取 → 领域转换 → Store 消费`，类比 React Query `select` 模式
- **Mock 数据驱动开发** — 工作台可脱离后端独立运行和演示
- **Zustand selector 不返回新对象** — `filter()`/`map()` 在 selector 中会导致无限重渲染，派生数据统一在 `useMemo` 钩子中计算

## 相关文档

- [用户操作手册](docs/用户操作手册.md)

## License

Copyright © 国能日新科技股份有限公司. All rights reserved.
