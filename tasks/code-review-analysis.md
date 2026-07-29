# 代码审查深度分析报告

> 生成日期：2026-07-24
> 审查范围：售后工单审核系统全栈（backend + frontend + docs）

---

## 总览

本次审查发现 **9 个问题**（8 个 P1 阻断性 + 1 个 P2 高风险），按性质分为 4 类：

| 类别 | 数量 | 严重程度 |
|------|------|----------|
| 安全漏洞（凭证泄露、认证配置、权限绕过） | 3 | 🔴 P1 阻断 |
| 数据库一致性问题（schema 不同步、迁移遗漏、列名大小写） | 3 | 🔴 P1 阻断 |
| 时区类型不匹配 | 1 | 🔴 P1 阻断 |
| 分布式可靠性缺陷（幂等性、持久化） | 2 | 🟡 P1/P2 |

---

## 逐条分析

### 1. [P1] 文档中的生产凭证泄露

**文件**: `docs/销售易服务工单接口文档.md:104-108`

**现状验证**:
```
| client_id     | YOUR_CLIENT_ID |
| client_secret | YOUR_CLIENT_SECRET |
| username      | YOUR_SALESEOUYI_USERNAME          |
| password      | YOUR_SALESEOUYI_PASSWORD                   |
```

**根因分析**: 该文档作为接口对接参考，将真实的 OAuth2 凭证（client_secret、username、password + 安全令牌）以明文硬编码。这些是销售易 CRM 系统的生产级访问凭证，不是测试环境的模拟数据。

**实际影响**:
1. 任何能读取该 Git 仓库的人（包括离职员工、外包人员）都可以获取这些凭证
2. 即使从当前 HEAD 删除，Git 历史中仍然保留（`a4c91e2` 及之前的 commit）
3. 攻击者可以调用销售易 API 创建、修改、删除工单数据
4. `password` 字段中包含 `YOUR_SALESEOUYI_PASSWORD`，符合企业密码模式，高度疑似真实凭证

**修复要求**:
- 立即在销售易管理后台吊销并轮换 `client_secret` 和 `password`
- 用占位符替换文档中的凭证（如 `YOUR_CLIENT_SECRET`）
- 使用 `git filter-branch` 或 `bfg-repo-cleaner` 从 Git 历史中清除
- 将凭证迁移到环境变量（`backend/.env` 已在用 `XIAOSHOUYI_CLIENT_SECRET` 等配置，确认未提交到仓库）

---

### 2. [P1] 生产构建默认关闭认证

**文件**: `frontend/.env:1`

**现状验证**:
```bash
VITE_AUTH_ENABLED=false
```
前端目录下不存在 `.env.development`、`.env.production` 等模式特定文件。

**根因分析**: Vite 的 `.env` 文件在**所有模式**下都会加载（`vite build` 和 `vite dev` 都读取）。`VITE_AUTH_ENABLED=false` 会被 `npm run build` 编译进生产 JS bundle，导致前端永远不触发 Keycloak 认证跳转，始终发送 `dev-token` header。

**触发链路**:
```
npm run build
  → Vite 加载 .env → VITE_AUTH_ENABLED=false 写入 process.env
  → 前端代码 if (import.meta.env.VITE_AUTH_ENABLED !== 'true') → 跳过认证
  → 所有 API 请求携带 dev-token header
  → 后端 AUTH_ENABLED=true（默认） → 拒绝 dev-token → 401 Unauthorized
  → 应用完全不可用
```

**修复方案**:
```
# 删除 frontend/.env 中的 VITE_AUTH_ENABLED=false

# 新建 frontend/.env.development（仅开发模式加载）:
VITE_AUTH_ENABLED=false
VITE_KEYCLOAK_URL=http://10.8.6.32:18080
VITE_KEYCLOAK_REALM=company-dev
VITE_KEYCLOAK_CLIENT_ID=shouhou-gongdan-web

# frontend/.env （所有模式通用，仅保留非敏感默认值）:
VITE_KEYCLOAK_URL=http://10.8.6.32:18080
VITE_KEYCLOAK_REALM=company-dev
VITE_KEYCLOAK_CLIENT_ID=shouhou-gongdan-web
```

---

### 3. [P1] ALLOWED_FIELDS 包含只读/系统字段导致越权更新

**文件**: 
- `backend/app/core/field_config.py:50-53` — `allowed_keys` 返回全部字段
- `backend/app/services/review_service.py:263-274` — 白名单过滤后直接 ORM UPDATE

**现状验证**:

`field_config.yaml` 中标记了以下不应被用户修改的字段，但它们全都在 `allowed_keys` 集合中：

| 字段 | 风险类型 | 只读标记 |
|------|---------|---------|
| `version` | 乐观锁绕过 | `readonly: true` |
| `status` | 审核状态破坏 | `readonly: true` |
| `serial_number` | 工单编号篡改 | `readonly: true` |
| `reject_count` | 驳回计数覆盖 | `readonly: true` |
| `last_reject_reason` | 驳回元数据覆盖 | `readonly: true` |
| `last_rejected_by` | 驳回元数据覆盖 | `readonly: true` |
| `last_rejected_at` | 驳回元数据覆盖 | `readonly: true` |
| `entityType` | 业务类型篡改 | `readonly: true` |
| `created_at` | 创建时间伪造 | `readonly: true` |
| `defectFlag__c` | 隐藏字段修改 | `ui_visible: false` |

**攻击链路**:

```
POST /api/workorders/WO001/confirm
{
  "session_id": "sess-xxx",
  "version": 5,
  "idempotency_key": "ik-xxx",
  "changes": [
    {"op": "replace", "path": "/version",    "new_value": 1},     // ← 通过白名单！
    {"op": "replace", "path": "/status",     "new_value": "pending_review"}, // ← 通过白名单！
    {"op": "replace", "path": "/defectFlag__c", "new_value": "0"}  // ← 通过白名单！
  ]
}

→ _execute_confirm 中:
  UPDATE workorder SET status = 'confirmed', version = version + 1 ...  // 乐观锁先执行
  UPDATE workorder SET version = 1, status = 'pending_review', ...       // 然后被变更覆盖！

→ 结果：工单状态回退 + 版本号被重置，审核流程被破坏
```

**核心问题**: `_execute_confirm` 分两步写入——先乐观锁 UPDATE，再对 `filtered_changes` 做批量 UPDATE。如果 filtered_changes 包含 `version`、`status` 等字段，第二次 UPDATE 会覆盖第一次的结果。

**修复方案**:
```python
# field_config.py — 新增方法
@property
def editable_keys(self) -> set[str]:
    """返回用户可编辑的字段 key 集合：排除 readonly、hidden、审核元数据。"""
    return {
        f.key for f in self.fields
        if not f.readonly and f.ui_visible
        and f.key not in {
            'version', 'status', 'serial_number',
            'reject_count', 'last_reject_reason', 'last_rejected_by', 'last_rejected_at',
            'review_notes', 'sync_status', 'sync_attempts', 'sync_last_error',
        }
    }

# review.py — ALLOWED_FIELDS 改用 editable_keys
ALLOWED_FIELDS: set[str] = load_field_config().editable_keys
```

---

### 4. [P1] Docker 初始化 schema 快照过时

**文件**: `backend/schema_init.sql:9-62`

**现状验证**:
- `schema_init.sql` 的 `workorder` 表定义使用的是**迁移前**的旧业务列（`station_name`、`dispatch_name`、`project_code` 等 28 个旧列）
- ORM 模型 `WorkOrder` 已全部替换为销售易 serviceCase API 字段（`ownerId`、`dimDepart` 等 34 个新列）
- `schema_init.sql` 缺少 `sync_attempts`、`sync_last_error` 列

**部署断链**:
```
README 指示的部署步骤:
  1. psql -f schema_init.sql          → 创建含旧列的表
  2. alembic stamp head               → 标记迁移为已执行，但不实际运行！
  3. 启动应用                         → ORM 查询 "ownerId" → column does not exist → CRASH
```

`alembic stamp head` 只是在 `alembic_version` 表中写入版本号，**不执行 DDL**。迁移 002 中的 `op.add_column` 永远不会运行，`"ownerId"` 等列根本不存在。

**修复方案**:
- 将 `schema_init.sql` 中的 `workorder` 建表语句替换为与 ORM 模型 + 迁移 002 一致的新列定义
- 补充 `sync_attempts`、`sync_last_error` 列
- 考虑在 CI 中加入 schema 一致性校验（对比 ORM 模型与 schema_init.sql 的列清单）

---

### 5. [P1] 迁移遗漏 relatedAttachment__c 列

**文件**: `backend/alembic/versions/002_replace_business_columns_with_servicecase.py:62-64`

**现状验证**:

迁移的 NEW_COLUMNS 列表（第 62-66 行）:
```python
('remark__c', sa.Text(), None),              # ← 第 62 行
('planFeedbackTime__c', sa.String(32), None), # ← 第 63 行
('requireSolveTime__c', sa.String(32), None), # ← 第 64 行
('defectFlag__c', sa.String(4), '1'),         # ← 第 66 行
```

而 ORM 模型中的字段顺序（`workorder.py:73-76`）:
```python
remark__c = Column(Text, nullable=True)                    # line 73
relatedAttachment__c = Column(String(255), nullable=True)  # line 74 ← 遗漏！
planFeedbackTime__c = Column(String(32), nullable=True)    # line 75
requireSolveTime__c = Column(String(32), nullable=True)    # line 76
```

**影响范围**:
- `relatedAttachment__c` 在 `field_config.yaml` 中有配置（描述 → 相关附件）
- `background_sync_to_xiaoshouyi` 在构建 `CreateWorkOrderRequest` 时读取该字段（第 95 行: `relatedAttachment__c=row.get("relatedAttachment__c") or ""`）
- 对已有环境执行 `alembic upgrade head` 后，该列不存在，任何 SELECT * 查询在 ORM 加载完整 `WorkOrder` 时会触发 `AttributeError` 或 asyncpg 报错
- 同步到销售易时该字段始终为空字符串（row.get 返回 None，变为 ""）

**修复**:
```python
# 在 remark__c 之后、planFeedbackTime__c 之前插入
('relatedAttachment__c', sa.String(255), None),
```

---

### 6. [P1] TIMESTAMP 时区类型不匹配

**文件**: 
- `backend/app/models/audit_log.py:20-21` — `DateTime` 不带 `timezone=True`
- `backend/app/services/audit_service.py:21,60` — 使用 `datetime.now(timezone.utc)`（带时区）
- `backend/app/services/bad_case_service.py:18` — 使用 `datetime.now(timezone.utc)`（带时区）

**现状验证**:

模型定义（audit_log.py）:
```python
operated_at = Column(DateTime, nullable=False, 
                     default=lambda: datetime.now(timezone.utc))
#                   ^^^^^^^^ timezone=False (默认值)
```

服务层写入（audit_service.py, bad_case_service.py）:
```python
now = datetime.now(timezone.utc)  # aware datetime: 2026-07-24T10:30:00+00:00
```

**冲突机制**:
```
Python: datetime.now(timezone.utc) 
  → 2026-07-24 10:30:00+00:00  (offset-aware)

SQLAlchemy Column: DateTime (timezone=False) 
  → PostgreSQL: TIMESTAMP WITHOUT TIME ZONE

asyncpg 写入路径:
  aware datetime → TIMESTAMP WITHOUT TIME ZONE
  → asyncpg.exceptions.InternalClientError: 
    "cannot encode timezone-aware datetime to type timestamp without time zone"
```

**注意**: 这个问题的具体表现取决于 SQLAlchemy + asyncpg 版本组合。某些版本的 SQLAlchemy 类型处理器会自动剥离时区信息，但这不是文档保证的行为，也不应在生产代码中依赖隐式转换。

**另外的隐患**: `review_service.py:255` 使用 `datetime.utcnow()`（Python 3.12+ 已废弃），产生 naive datetime。这在当前代码路径中恰好不会触发问题（因为是 raw SQL + 参数绑定），但与 `audit_service.py` 中的 `datetime.now(timezone.utc)` 风格不一致，容易在重构时引入错误。

**修复方案**（统一选择其一）:

方案 A: 模型 + 迁移改为 `timezone=True`（推荐）
```python
# audit_log.py
operated_at = Column(DateTime(timezone=True), nullable=False, 
                     default=lambda: datetime.now(timezone.utc))

# bad_case.py — 同样改为 timezone=True
created_at = Column(DateTime(timezone=True), nullable=False, 
                     default=lambda: datetime.now(timezone.utc))

# 迁移中对应改为 TIMESTAMP WITH TIME ZONE
```

方案 B: 统一使用 naive UTC
```python
operated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
```

---

### 7. [P1] 销售易同步缺少真实幂等性

**文件**: `backend/app/services/review_service.py:31-34` → 整个 `background_sync_to_xiaoshouyi` 函数

**现状验证**:

`ConfirmRequest` 携带 `idempotency_key`:
```python
class ConfirmRequest(BaseModel):
    idempotency_key: str  # 前端生成
```

`confirm()` 方法将其传给 `ConfirmResult.sync_idempotency_key`:
```python
sync_key = request.idempotency_key  # line 406
return ConfirmResult(response=result_dict, sync_idempotency_key=sync_key)
```

`background_sync_to_xiaoshouyi` 接收 `sync_idempotency_key` 参数:
```python
async def background_sync_to_xiaoshouyi(
    workorder_id: str,
    sync_idempotency_key: str,  # ← 接收了但从未使用！
    session_factory: async_sessionmaker,
) -> str:
```

在整个函数体中，`sync_idempotency_key` **从头到尾没有被引用**。销售易 `insertServiceCase` API 调用也没有传递任何幂等键。

**重复工单创建场景**:
```
时间线:
  T1: POST /confirm → 本地事务提交 (sync_status='pending')
  T2: background_sync_to_xiaoshouyi 开始执行
  T3: 销售易 API 请求发出 → insertServiceCase
  T4: 销售易成功创建工单 (external_id=SC-001)，返回 HTTP 200
  T5: 网络波动，HTTP 响应在到达服务器前超时
  T6: async wait_for 抛出 TimeoutError
  T7: 重试 → 再次 POST insertServiceCase（无幂等键！）
  T8: 销售易再次创建工单 (external_id=SC-002) → 重复工单！

或者更糟:
  T1-T4: 同上
  T5: 进程在此刻崩溃
  T6: 管理员调用 POST /admin/sync-failures/xxx/retry
  T7: background_sync_to_xiaoshouyi 再次执行
  T8: insertServiceCase 再次调用 → 重复工单！
```

**修复方向**（按优先级排序）:
1. **最佳**: 确认销售易 API 是否支持幂等键（如 `Idempotency-Key` header 或请求体中的 `requestId` 字段），使用 `sync_idempotency_key` 传参
2. **次选**: 首次调用前将 `sync_idempotency_key` 持久化到 `workorder` 表，同步前先查询销售易是否已有使用该键的工单
3. **兜底**: 在 `sync_status='syncing'` 被意外中断时，启动时基于外部系统状态进行对账

---

### 8. [P2] 后台同步任务不持久化（进程内 BackgroundTasks）

**文件**: `backend/app/routers/review.py:118-125`

**现状验证**:
```python
if result.sync_idempotency_key is not None:
    background_tasks.add_task(      # FastAPI BackgroundTasks — 进程内运行
        background_sync_to_xiaoshouyi,
        workorder_id,
        result.sync_idempotency_key,
        async_session,
    )
```

**数据丢失场景**:
```
T1: 本地事务已提交，sync_status = 'pending'
T2: HTTP 200 已返回给前端（前端显示"同步中"）
T3: BackgroundTasks 开始执行 background_sync_to_xiaoshouyi
T4: 进程被 OOM Killer 终止 / k8s pod 被驱逐 / systemd 重启

结果:
  - sync_status 永久停留在 'pending'
  - 管理 API 只允许重试 'failed' 状态:
    if wo.sync_status != 'failed':
        raise HTTPException(... "只有 'failed' 状态可以重试")
  - 运维人员无法通过管理界面恢复
  - 只能手动登录数据库修改状态
```

**影响扩大**: 如果同一批次确认了多个工单，所有在崩溃时处于 `pending` 或 `syncing` 的记录都会成为孤儿。

**修复方案**:

短期（无需引入新中间件）:
```python
# 启动时执行一次恢复查询
async def recover_orphan_syncs(session_factory):
    async with session_factory() as db:
        result = await db.execute(
            select(WorkOrder).where(
                WorkOrder.sync_status.in_(['pending', 'syncing'])
            )
        )
        orphans = result.scalars().all()
        for wo in orphans:
            # 重新入队或标记为 failed
            ...
```

长期（生产就绪）:
- 引入持久化任务队列（Celery + Redis/RabbitMQ、ARQ、或 PostgreSQL-backed queue）
- 实现 outbox 模式：确认时写入 `outbox` 表，独立 worker 轮询发送
- 或使用轻量方案：`apscheduler` 定时扫描 `pending/syncing` 记录并重试

---

### 9. [P2] init_pg.py 中混合大小写列名未加引号

**文件**: `backend/init_pg.py:30-34`

**现状验证**:

`init_pg.py` 中的 DDL（无引号）:
```sql
ownerId                 VARCHAR(64)     NULL,   -- PostgreSQL 折叠为 ownerid
dimDepart               VARCHAR(128)    NULL,   -- PostgreSQL 折叠为 dimdepart
entityType              VARCHAR(32)     NULL,   -- → entitytype
feedbackChannel__c      VARCHAR(32)     NULL,   -- → feedbackchannel__c (小写+下划线不受影响)
```

PostgreSQL 的标识符折叠规则:
- 未加引号的标识符 → 折叠为小写
- 加了双引号的标识符 → 保留原始大小写

SQLAlchemy ORM 对包含大写字母的 Column 名会自动加引号:
```python
ownerId = Column(String(64))  # → SELECT "ownerId" FROM workorder
```

**结果**:
```
init_pg.py 创建的列: ownerid (小写)
ORM 查询的列:       "ownerId" (大小写敏感)
→ PostgreSQL: column "ownerId" does not exist
```

**影响范围**: 所有包含大写字母的列名（`ownerId`、`dimDepart`、`entityType`、`caseSource`、`caseStatus`、`caseAccountId` 等约 12 个列）。

**注意**: 通过 Alembic 迁移 002 创建的表不会有此问题，因为 SQLAlchemy 会自动为混合大小写列名添加双引号。只有使用 `init_pg.py` 裸 DDL 初始化的数据库才会出现此问题。

**修复**:
```sql
-- 所有含大写字母的列名加双引号
"ownerId"                 VARCHAR(64)     NULL,
"dimDepart"               VARCHAR(128)    NULL,
"entityType"              VARCHAR(32)     NULL DEFAULT '11010045500001',
-- ... 等等
```

或者统一改为全小写 + 下划线（需要同步修改 ORM 模型、schema、API 映射）。

---

## 依赖关系与修复顺序

```
第1步: 凭证轮换（安全问题，必须最先处理）
  ├── 1. 销售易后台吊销/轮换 client_secret + password
  ├── 2. 清理文档 + Git 历史
  └── 3. 确认 .env 中的 XIAOSHOUYI_* 凭证未提交

第2步: Schema 修复（后续修复依赖正确的表结构）
  ├── 5. 迁移 002 补 relatedAttachment__c
  ├── 4. schema_init.sql 重写为新的列定义
  ├── 9. init_pg.py 列名加引号
  └── 6. 模型 + 迁移改为 timezone=True

第3步: 安全加固
  ├── 2. .env → .env.development 拆分
  └── 3. ALLOWED_FIELDS 排除只读/系统字段

第4步: 可靠性增强
  ├── 7. 销售易同步幂等性
  └── 8. 持久化任务 / 启动恢复
```

---

## 总结

这 9 个问题全部经过代码验证确认存在，属于真实缺陷而非误报。其中：

- **问题 #1（凭证泄露）** 是紧急安全事件，应当**立即处理**，不等其他修复
- **问题 #3（越权更新）** 是权限模型的结构性缺陷，当前任何认证用户都可以修改版本号和审核状态
- **问题 #4、#5、#6、#9** 共同构成了"新环境部署即故障"的局面——按当前文档部署的应用在首次查询时就会崩溃
- **问题 #7、#8** 在低负载测试环境不会暴露，但在生产环境的网络波动或服务重启中会导致数据重复或丢失

建议在修复上述问题前，不要将此版本部署到生产环境。
