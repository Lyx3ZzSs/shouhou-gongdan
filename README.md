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
| **中间工作区** | 35 个字段分 8 组展示，diff 对比视图，行内编辑，逐字段确认 |
| **右侧控制台** | 审核进度、当前变更、备注记录 |

**交互特性：**
- 键盘快捷键全程操作（J/K 导航、Cmd+Enter 提交、Cmd+S 暂存等）
- 字段级异常高亮（阻断/告警/建议），一键跳转定位
- Diff 对比视图（原值 → 现值），hover 显示操作按钮
- 密度模式切换（标准/紧凑），响应式布局适配小屏
- 分布式编辑锁防并发冲突，版本冲突检测与提醒
- 自动暂存草稿，切换工单未保存提醒
- 认证集成：Keycloak 统一身份认证 + 开发模式 Mock 切换

### 审核后端服务

- **工单审核** — 确认/驳回双分支，乐观锁版本控制，幂等防重
- **字段级审计日志** — 记录每次字段变更的修改人、修改原因、前后值
- **Bad Case 回流** — 人工修正的字段自动入库，用于 AI 模型持续训练
- **分布式编辑锁** — Redis Lua 脚本原子操作，5 分钟 TTL 自动释放，心跳续期
- **Keycloak JWT 认证** — OIDC 协议，角色鉴权（agent_admin / agent_manager / agent_user）
- **销售易同步** — 审核确认后异步同步至销售易 serviceCase API，失败自动重试
- **孤儿同步恢复** — 启动时自动恢复崩溃遗留的 pending/syncing 记录
- **审核统计** — 按人、按状态、趋势、耗时分布的多维度统计接口

## 技术栈

| 层 | 技术 |
|----|------|
| **后端框架** | Python 3.13 + FastAPI |
| **ORM** | SQLAlchemy 2.0 (async) |
| **数据库** | PostgreSQL 16 (开发/生产统一) |
| **缓存** | Redis 7+ (分布式锁) |
| **认证** | Keycloak OIDC (开发环境可关闭) |
| **前端框架** | React 18 + TypeScript 5 |
| **构建工具** | Vite 5 |
| **样式方案** | Tailwind CSS 3.4 + shadcn/ui 组件 |
| **状态管理** | Zustand 5 |
| **UI 原语** | Radix UI (无障碍组件) |
| **动画** | Framer Motion |
| **测试** | pytest (后端) + Vitest (前端) |

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- Docker Compose（用于启动 PostgreSQL + Redis）

### 1. 启动基础设施

```bash
# 设置数据库密码（首次运行）
export POSTGRES_PASSWORD=<强随机密码>
export REDIS_PASSWORD=<强随机密码>

# 启动 PostgreSQL + Redis（自动执行 schema_init.sql 建表）
docker compose up -d
```

### 2. 启动后端

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 配置环境变量（开发环境可直接使用 .env）
cp .env.example .env   # 首次运行

# 启动服务 (端口 8093)
python -m app.main
```

### 3. 启动前端

```bash
cd frontend
npm install

# 开发模式启动 (端口 5193)
npm run dev
```

Vite 自动将 `/api` 代理到 `http://localhost:8093`。

### 开发模式认证

默认关闭 Keycloak 认证，使用 Mock 用户：
- 后端 `.env`: `AUTH_ENABLED=false`
- 前端 `.env.development`: `VITE_AUTH_ENABLED=false`

### 运行测试

```bash
# 后端
cd backend && pytest

# 前端
cd frontend && npx vitest run

# TypeScript 类型检查
cd frontend && npm run typecheck
```

### 生成 API 类型

```bash
# 后端生成 OpenAPI spec
cd backend && python scripts/generate_openapi.py

# 前端生成 TypeScript 类型
cd ../frontend && npm run generate-types
```

## 项目结构

```
├── schema_init.sql              # 数据库初始化 DDL（PostgreSQL）
├── docker-compose.yml           # 开发环境基础设施
├── backend/
│   ├── app/
│   │   ├── auth/                # Keycloak JWT 认证与角色鉴权
│   │   ├── clients/             # 外部 API 客户端（销售易）
│   │   ├── core/                # 配置、数据库连接、字段配置
│   │   ├── models/              # SQLAlchemy ORM 模型
│   │   ├── routers/             # FastAPI 路由 (review, lock, stats)
│   │   ├── schemas/             # Pydantic 请求/响应模型
│   │   └── services/            # 业务逻辑 (审核、锁、统计、导入、同步)
│   ├── alembic/                 # 数据库迁移脚本
│   ├── tests/                   # pytest 测试套件
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── auth/                # 认证模块 (KeycloakProvider, MockAuth, JWT 解析)
│   │   ├── api/                 # API 客户端 (authFetch + 自动 token 刷新)
│   │   ├── workbench/           # 审核工作台
│   │   │   ├── components/
│   │   │   │   ├── queue/       # 左侧队列面板
│   │   │   │   ├── workspace/   # 中间审核工作区（FieldCard, Diff, 行内编辑）
│   │   │   │   ├── sidebar/     # 右侧控制台
│   │   │   │   └── primitives/  # 基础 UI 组件（Badge, SLA 倒计时, 自动保存指示）
│   │   │   ├── hooks/           # 自定义 Hooks (autoSave)
│   │   │   ├── store/           # Zustand 状态管理
│   │   │   ├── lib/             # 工具函数、常量、数据转换
│   │   │   ├── mock/            # Mock 数据（开发演示用）
│   │   │   └── types.ts         # 工作台类型定义
│   │   ├── stats/               # 审核统计页面
│   │   ├── components/ui/       # shadcn/ui 基础组件
│   │   └── lib/                 # 通用工具 (cn, animations, glass)
│   ├── tests/                   # Vitest 测试
│   └── package.json
└── docs/                        # 项目文档
```

## 数据库

### Schema 概览

| Schema | 表/视图 | 说明 |
|--------|---------|------|
| `public` | `workorder_review` | 审核元数据（状态、版本、同步信息） |
| `public` | `workorder_audit_log` | 字段级审计日志 |
| `public` | `bad_case_sample` | AI 坏例样本（模型回流） |
| `public` | `workorder_stash` | 审核进度暂存 |
| `public` | `v_ticket` | 工单业务数据视图（只读） |
| `ticket_source` | `ticket` | 工单原始业务数据（销售易字段） |
| `ticket_source` | `project_info` | 项目信息 |
| `ticket_source` | `source_message` | 消息来源 |
| `ticket_source` | `wechat_user` | 微信用户 |
| `ticket_source` | `ticket_attachment` | 工单附件 |

完整 DDL 见根目录 `schema_init.sql`，与 ORM 模型严格同步。

## API 端点

### 工单审核

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/workorders` | 工单列表（分页） |
| `GET` | `/api/workorders/{id}` | 工单详情（合并 v_ticket 业务字段） |
| `POST` | `/api/workorders/{id}/review` | 提交审核（确认/驳回，会触发销售易同步） |
| `POST` | `/api/workorders/{id}/confirm` | 确认提交（异步同步至销售易） |
| `GET` | `/api/workorders/{id}/audit-logs` | 审核审计日志 |

### 编辑锁

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/workorders/{id}/lock` | 获取分布式编辑锁 |
| `PUT` | `/api/workorders/{id}/lock` | 锁心跳续期 |
| `DELETE` | `/api/workorders/{id}/lock` | 释放编辑锁 |

### 暂存

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/workorders/{id}/stash` | 保存审核进度（支持 manual / auto_save 模式） |
| `GET` | `/api/workorders/{id}/stash` | 获取暂存数据 |
| `DELETE` | `/api/workorders/{id}/stash` | 删除暂存数据 |

### 管理员

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/admin/import` | 从 ticket_source 导入工单到审核表 |
| `GET` | `/api/admin/sync-failures` | 查询销售易同步失败记录 |
| `POST` | `/api/admin/retry-sync/{id}` | 重试同步 |

### 统计

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/stats/overview` | 审核总览统计 |
| `GET` | `/api/stats/by-reviewer` | 按审核人统计 |
| `GET` | `/api/stats/trend` | 审核趋势 |
| `GET` | `/api/stats/duration` | 审核耗时分布 |
| `GET` | `/api/stats/status` | 工单状态分布 |

## 架构决策

- **三栏布局** — 队列 → 审核区 → 控制台，适配复杂工单的字段级审核需求
- **乐观锁** — 版本号防并发提交，冲突时提示用户刷新
- **锁 release 始终在 finally 中执行** — 防止孤儿锁阻塞队列
- **三层数据管线** — `API 获取 → 领域转换 → Store 消费`，类比 React Query `select` 模式
- **Mock 数据驱动开发** — 工作台可脱离后端独立运行和演示
- **Zustand selector 不返回新对象** — `filter()`/`map()` 在 selector 中会导致无限重渲染，派生数据统一在 `useMemo` 钩子中计算
- **Token 自动刷新** — 前端 authFetch 在 401 时自动尝试 refresh，失败后跳转 Keycloak 登录
- **认证可关闭** — 本地开发通过 `AUTH_ENABLED=false` 跳过 Keycloak，使用默认开发用户

## 相关文档

- [用户操作手册](docs/用户操作手册.md)
- [系统架构设计文档](docs/系统架构设计文档.md)
- [销售易服务工单接口文档](docs/销售易服务工单接口文档.md)

## License

Copyright © 国能日新科技股份有限公司. All rights reserved.
