# 售后工单审核工作台

> **AI 售后智能服务一体化平台** 的子项目 — 负责 AI 生成工单的人工审核与修正回流。

## 项目背景

新能源行业售后服务渠道碎片化（400 电话、企业微信、邮件、小程序），业务复杂度高（算法、气象、考核规则），跨部门协同频繁，工单量已超出人工处理能力。

"AI 售后智能服务一体化平台"通过 AI 自动生成受理单 + 人工审核确认的协作模式，提升工单处理效率与质量。**本项目为其中的人工审核工作台部分**，核心职责是：

- 提供聚焦六个关键字段的桌面审核界面，普通字段只读、异常集中处理
- 将人工修正数据通过 Bad Case 回流机制反哺 AI 模型，形成持续优化闭环

## 功能概览

### 工单审核工作台（前端）

单任务审核界面，支持客服人员高效核对 AI 生成的工单：

| 区域 | 功能 |
|------|------|
| **全局导航** | 概览、开始审核、稍后处理、工单搜索、审核统计、同步失败 |
| **审核工作区** | FIFO 领取下一单；只编辑场站、项目、责任人、反馈人、联系方式和描述 |
| **核对材料** | 原始对话、附件、客户/项目台账集中查看 |
| **底部决策栏** | 跳过、暂存、驳回、审核通过 |

**交互特性：**
- 服务端 FIFO 领单，Redis 编辑锁避免多人领取同一张工单
- 阻断问题集中展示；非关键字段问题可直接驳回上游补充
- Diff 对比视图（原值 → 现值），hover 显示操作按钮
- 分布式编辑锁防并发冲突，版本冲突检测与提醒
- 自动暂存草稿，关闭时明确选择暂存或放弃
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

### Schema 概览（全部在 public）

| 表/视图 | 说明 |
|---------|------|
| `workorder_review` | 审核元数据（状态、版本、同步信息） |
| `workorder_audit_log` | 字段级审计日志 |
| `bad_case_sample` | AI 坏例样本（模型回流） |
| `workorder_stash` | 审核进度暂存 |
| `review_submission` | 确认/驳回幂等结果 |
| `ticket` | 工单原始业务数据（销售易字段，外部写入只读） |
| `project_info` | 项目信息 |
| `source_message` | 消息来源 |
| `wechat_user` | 微信用户 |
| `wechat_session` | 微信会话及原始消息 |
| `user_ledger` | 客户、场站与项目台账 |
| `beisen_employee_cache` | 员工和部门映射缓存 |
| `ticket_attachment` | 工单附件 |
| `ticket_view` | 【服务工单】唯一视图，基于 8 表输出规范业务字段 |

> 8 张工单源表由外部管道写入、本系统只读。应用连接 `customer_service_ticket`，仅写审核自有表；`ticket_view` 是唯一业务读取入口并保持销售易字段名契约。

空库/集成测试完整 DDL 见根目录 `schema_init.sql`。已有 8 表环境使用
`backend/scripts/migrate_current_ticket_schema.sql`，该脚本不修改源表，只创建审核表、索引和 `ticket_view`。
`backend/alembic/` 为遗留迁移，不参与当前部署。

现有环境升级需依次执行 `backend/scripts/migrate_phase1_trust.sql` 和
`backend/scripts/migrate_phase2_concurrency.sql`。第二阶段迁移为审核元数据增加
Redis 锁 fencing token，应用升级前必须先完成该幂等迁移。

运行探针：`GET /health` 仅检查进程存活；`GET /ready` 同时检查 PostgreSQL 与
Redis，任一依赖不可用时返回 503。生产负载均衡和 Kubernetes readinessProbe
应使用 `/ready`，livenessProbe 使用 `/health`。

## API 端点

### 工单审核

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/workorders` | 工单列表（分页） |
| `POST` | `/api/workorders/next` | FIFO 领取下一张未锁定工单 |
| `GET` | `/api/workorders/{id}` | 工单详情（合并 ticket_view 业务字段） |
| `GET` | `/api/workorders/{id}/context` | 原始对话、附件和客户/项目台账 |
| `GET` | `/api/workorders/lookups/stations` | 场站与项目候选项 |
| `GET` | `/api/workorders/lookups/employees` | 北森员工与部门候选项 |
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
| `POST` | `/api/admin/import` | 从 ticket 导入工单到审核表 |
| `GET` | `/api/admin/sync-failures` | 查询销售易同步失败记录 |
| `POST` | `/api/admin/sync-failures/{id}/retry` | 重试同步 |
| `POST` | `/api/admin/sync-uncertain/{id}/reconcile` | 确认已创建并绑定销售易单号 |
| `POST` | `/api/admin/sync-uncertain/{id}/confirm-not-created` | 确认未创建并转为可重试状态 |

### 统计

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/stats/overview` | 审核总览统计 |
| `GET` | `/api/stats/by-reviewer` | 按审核人统计 |
| `GET` | `/api/stats/trend` | 审核趋势 |
| `GET` | `/api/stats/duration` | 审核耗时分布 |
| `GET` | `/api/stats/status` | 工单状态分布 |

## 架构决策

- **单任务工作台** — 队列不常驻，只呈现当前工单、六个关键字段和决策动作
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
