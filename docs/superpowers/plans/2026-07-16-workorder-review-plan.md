# AI 工单审查页面 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 AI 工单审查页面，包含字段级变更追踪、审计日志、bad_case 回流、编辑锁定。

**Architecture:** React + FastAPI + MySQL 8.0 + Redis。后端遵循 router → service → model 三层；前端采用 Formily JSON Schema 驱动表单，并排展示 AI 原值与坐席编辑。

**Tech Stack:** React 18+, Formily 2.x, @formily/antd, lodash.isequal, FastAPI, SQLAlchemy 2.0 (async), Redis (aioredis), Pydantic v2, MySQL 8.0

## Global Constraints

- 所有 API 端点通过 JWT Bearer Token 认证，operator_id 从 token 提取
- 仅 `customer_service_agent` 角色可调用审查接口
- 坐席只能审查分配至本部门的工单
- 后端 UPDATE 必须使用 ALLOWED_FIELDS 白名单过滤
- 字段级变更以 JSON Patch 格式（op/path/old_value/new_value）记录
- bad_case 仅在 confirmed + 有实际变更时写入
- 合约要求：TDD (先写测试 → 再实现)、每个任务独立可测试

---

### Task 1: 数据库迁移 — 审计日志表 + bad_case 表 + 工单字段扩展

**Files:**
- Create: `backend/alembic/versions/001_add_review_tables.py`
- Create: `backend/app/models/audit_log.py`
- Create: `backend/app/models/bad_case.py`
- Modify: `backend/app/models/workorder.py` (add version, review, reject columns)

**Interfaces:**
- Produces: `WorkOrderAuditLog` model, `BadCaseSample` model, `WorkOrder.version`, `WorkOrder.reviewed_at`, `WorkOrder.reviewed_by`, `WorkOrder.reject_count`, `WorkOrder.last_reject_reason`, `WorkOrder.last_rejected_by`, `WorkOrder.last_rejected_at`

- [ ] **Step 1: 创建 WorkOrderAuditLog 模型**

```python
# backend/app/models/audit_log.py
from sqlalchemy import Column, BigInteger, String, Text, DECIMAL, DateTime, Index
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime

class Base(DeclarativeBase):
    pass

class WorkOrderAuditLog(Base):
    __tablename__ = "workorder_audit_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    workorder_id = Column(String(64), nullable=False)
    session_id = Column(String(64), nullable=False)
    field_path = Column(String(128), nullable=False)
    field_label = Column(String(64), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    change_type = Column(String(16), nullable=False, default="replace")
    ai_confidence = Column(DECIMAL(5, 4), nullable=True)
    operator_id = Column(String(64), nullable=False)
    operator_name = Column(String(64), nullable=True)
    operated_at = Column(DateTime(3), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_workorder", "workorder_id"),
        Index("idx_session", "session_id"),
        Index("idx_operator", "operator_id"),
        Index("idx_operated_at", "operated_at"),
    )
```

- [ ] **Step 2: 创建 BadCaseSample 模型**

```python
# backend/app/models/bad_case.py
from sqlalchemy import Column, BigInteger, String, Text, DECIMAL, DateTime, ForeignKey, Index
from .audit_log import Base
from datetime import datetime

class BadCaseSample(Base):
    __tablename__ = "bad_case_sample"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    workorder_id = Column(String(64), nullable=False)
    audit_log_id = Column(BigInteger, ForeignKey("workorder_audit_log.id"), nullable=False)
    field_path = Column(String(128), nullable=False)
    ai_value = Column(Text, nullable=True)
    human_value = Column(Text, nullable=True)
    ai_confidence = Column(DECIMAL(5, 4), nullable=True)
    sample_status = Column(String(16), nullable=False, default="pending")
    source = Column(String(16), nullable=False, default="review_correction")
    created_at = Column(DateTime(3), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_status", "sample_status"),
        Index("idx_workorder", "workorder_id"),
    )
```

- [ ] **Step 3: 扩展 WorkOrder 模型**

```python
# backend/app/models/workorder.py — 在现有 WorkOrder 类中增加以下列
from sqlalchemy import Column, Integer, String, DateTime, Text

# 新增:
version = Column(Integer, default=1, nullable=False)
reviewed_at = Column(DateTime(3), nullable=True)
reviewed_by = Column(String(64), nullable=True)
reject_count = Column(Integer, default=0, nullable=False)
last_reject_reason = Column(Text, nullable=True)
last_rejected_by = Column(String(64), nullable=True)
last_rejected_at = Column(DateTime(3), nullable=True)
```

- [ ] **Step 4: 编写 Alembic 迁移并运行**

```bash
cd backend
alembic revision --autogenerate -m "add review audit tables"
alembic upgrade head
```

- [ ] **Step 5: 验证迁移**

```bash
cd backend
python -c "
from app.models.audit_log import WorkOrderAuditLog
from app.models.bad_case import BadCaseSample
from app.models.workorder import WorkOrder
print('WorkOrder.version:', WorkOrder.version.type)
print('WorkOrderAuditLog:', WorkOrderAuditLog.__tablename__)
print('BadCaseSample:', BadCaseSample.__tablename__)
"
```

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/001_add_review_tables.py backend/app/models/
git commit -m "feat: add audit_log, bad_case models and workorder review columns"
```

---

### Task 2: Pydantic Schemas — 审查请求/响应 + 变更记录

**Files:**
- Create: `backend/app/schemas/review.py`

**Interfaces:**
- Produces: `FieldChange`, `ReviewRequest`, `ReviewResponse`, `AuditLogEntry`, `ALLOWED_FIELDS`

- [ ] **Step 1: 编写测试**

```python
# backend/tests/test_schemas.py
import pytest
from app.schemas.review import FieldChange, ReviewRequest, ALLOWED_FIELDS

def test_field_change_valid():
    fc = FieldChange(
        op="replace",
        path="/problem_category_l1",
        field_label="问题分类",
        old_value="数据问题",
        new_value="工程问题",
        ai_confidence=0.72,
    )
    assert fc.op == "replace"
    assert fc.old_value == "数据问题"

def test_review_request_confirm():
    req = ReviewRequest(
        session_id="sess-001",
        version=1,
        changes=[
            FieldChange(
                op="replace", path="/problem_category_l1",
                field_label="问题分类", old_value="数据问题",
                new_value="工程问题", ai_confidence=0.72,
            )
        ],
        reject_reason=None,
    )
    assert req.reject_reason is None
    assert len(req.changes) == 1

def test_review_request_reject():
    req = ReviewRequest(
        session_id="sess-002",
        version=1,
        changes=[],
        reject_reason="分类与客户描述不符",
    )
    assert req.reject_reason == "分类与客户描述不符"

def test_allowed_fields_contains_required():
    assert "station_name" in ALLOWED_FIELDS
    assert "problem_category_l1" in ALLOWED_FIELDS
    assert "responsible_person" in ALLOWED_FIELDS
    assert "order_level" in ALLOWED_FIELDS
    assert "customer_level" in ALLOWED_FIELDS
    assert "product_type" in ALLOWED_FIELDS

def test_field_change_rejects_invalid_op():
    with pytest.raises(ValueError):
        FieldChange(
            op="invalid",
            path="/x",
            field_label="X",
            old_value=None,
            new_value=None,
        )
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend && pytest tests/test_schemas.py -v
# Expected: all FAIL — module not found
```

- [ ] **Step 3: 实现 Schemas**

```python
# backend/app/schemas/review.py
from pydantic import BaseModel, field_validator
from typing import Any, Literal

ALLOWED_FIELDS = {
    "station_name", "dispatch_name", "project_code", "project_name",
    "project_province", "customer_name", "problem_description", "feedback_channel",
    "product_line", "product_category", "product_type", "customer_level",
    "problem_category_l1", "problem_category_l2", "problem_category_l3",
    "order_type", "problem_type", "fault_category", "fault_detail",
    "responsible_person", "responsible_department", "primary_department",
    "after_sales_person", "transferred_person", "transferred_department",
    "order_level", "fault_level", "onsite_level", "required_solve_time",
}


class FieldChange(BaseModel):
    op: Literal["replace", "add", "remove"]
    path: str
    field_label: str
    old_value: Any | None = None
    new_value: Any | None = None
    ai_confidence: float | None = None

    @field_validator("path")
    @classmethod
    def path_must_start_with_slash(cls, v: str) -> str:
        if not v.startswith("/"):
            raise ValueError("path must start with '/'")
        return v


class ReviewRequest(BaseModel):
    session_id: str
    version: int
    changes: list[FieldChange] = []
    reject_reason: str | None = None


class AuditLogEntry(BaseModel):
    session_id: str
    operator_name: str
    operated_at: str
    changes: list[FieldChange]


class ReviewResponse(BaseModel):
    review_id: str
    workorder_id: str
    status: Literal["confirmed", "rejected"]
    change_count: int
    bad_case_count: int
    next_status: str
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend && pytest tests/test_schemas.py -v
# Expected: all PASS
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/review.py backend/tests/test_schemas.py
git commit -m "feat: add review Pydantic schemas and ALLOWED_FIELDS"
```

---

### Task 3: Auth 依赖注入 — get_current_user

**Files:**
- Create: `backend/app/auth/dependencies.py`

**Interfaces:**
- Produces: `CurrentUser` dataclass, `get_current_user()` FastAPI dependency
- Consumes: JWT Bearer token from Authorization header

- [ ] **Step 1: 编写测试**

```python
# backend/tests/test_auth.py
import pytest
from unittest.mock import patch, AsyncMock
from app.auth.dependencies import get_current_user, CurrentUser

@pytest.mark.asyncio
async def test_get_current_user_from_valid_token():
    """operator_id 从 JWT token payload 提取，非客户端传入"""
    mock_db = AsyncMock()
    token = "Bearer eyJ.valid.token"
    with patch("app.auth.dependencies.decode_jwt") as mock_decode:
        mock_decode.return_value = {
            "sub": "agent-001",
            "name": "张三",
            "role": "customer_service_agent",
            "department": "售后部",
        }
        user = await get_current_user(token=token, db=mock_db)
        assert user.user_id == "agent-001"
        assert user.name == "张三"
        assert user.role == "customer_service_agent"
        assert user.department == "售后部"

@pytest.mark.asyncio
async def test_get_current_user_rejects_non_agent_role():
    mock_db = AsyncMock()
    token = "Bearer eyJ.valid.token"
    with patch("app.auth.dependencies.decode_jwt") as mock_decode:
        mock_decode.return_value = {
            "sub": "user-001",
            "name": "李四",
            "role": "viewer",
            "department": "售后部",
        }
        with pytest.raises(Exception) as exc:
            await get_current_user(token=token, db=mock_db)
        assert "403" in str(exc.value) or "Forbidden" in str(exc.value)
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend && pytest tests/test_auth.py -v
# Expected: FAIL — module not found
```

- [ ] **Step 3: 实现 auth dependency**

```python
# backend/app/auth/dependencies.py
from dataclasses import dataclass
from fastapi import Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

security = HTTPBearer()


@dataclass
class CurrentUser:
    user_id: str
    name: str
    role: str
    department: str


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    token = credentials.credentials
    payload = decode_jwt(token)
    user = CurrentUser(
        user_id=payload["sub"],
        name=payload.get("name", ""),
        role=payload.get("role", ""),
        department=payload.get("department", ""),
    )
    if user.role != "customer_service_agent":
        raise HTTPException(status_code=403, detail="仅客服坐席可执行此操作")
    return user


def decode_jwt(token: str) -> dict:
    # TODO: 替换为实际的 JWT 解码逻辑（项目级配置）
    import jwt
    from app.core.config import settings
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend && pytest tests/test_auth.py -v
# Expected: PASS
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/ backend/tests/test_auth.py
git commit -m "feat: add get_current_user auth dependency with role check"
```

---

### Task 4: 编辑锁定 API — POST/DELETE/PUT /lock

**Files:**
- Create: `backend/app/services/lock_service.py`
- Create: `backend/app/routers/lock.py`

**Interfaces:**
- Consumes: `CurrentUser` from Task 3, Redis client
- Produces: `POST /api/workorders/{id}/lock`, `DELETE /api/workorders/{id}/lock`, `PUT /api/workorders/{id}/lock`

- [ ] **Step 1: 编写测试**

```python
# backend/tests/test_lock_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.auth.dependencies import CurrentUser

@pytest.fixture
def mock_current_user():
    return CurrentUser(user_id="agent-001", name="张三", role="customer_service_agent", department="售后部")

@pytest.fixture
async def client(mock_current_user):
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_acquire_lock_success(client):
    """首次获取锁成功"""
    resp = await client.post("/api/workorders/WO001/lock")
    assert resp.status_code == 200
    data = resp.json()
    assert data["locked"] is True
    assert data["owner"] == "张三"

@pytest.mark.asyncio
async def test_acquire_lock_returns_owner_when_locked_by_other(client):
    """锁已被他人持有时返回持有者信息"""
    # 先由 agent-002 获取锁
    import redis.asyncio as aioredis
    r = aioredis.from_url("redis://localhost")
    await r.set("review_lock:WO002", "agent-002:李四:2026-07-16T10:00:00", ex=300)
    resp = await client.post("/api/workorders/WO002/lock")
    assert resp.status_code == 200
    data = resp.json()
    assert data["locked"] is False
    assert data["owner"] == "李四"

@pytest.mark.asyncio
async def test_release_lock_only_by_owner(client):
    """非持有者释放锁返回 403"""
    import redis.asyncio as aioredis
    r = aioredis.from_url("redis://localhost")
    await r.set("review_lock:WO003", "agent-002:李四:2026-07-16T10:00:00", ex=300)
    resp = await client.delete("/api/workorders/WO003/lock")
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_heartbeat_only_by_owner(client):
    """非持有者心跳续期返回 423"""
    import redis.asyncio as aioredis
    r = aioredis.from_url("redis://localhost")
    await r.set("review_lock:WO004", "agent-002:李四:2026-07-16T10:00:00", ex=300)
    resp = await client.put("/api/workorders/WO004/lock")
    assert resp.status_code == 423
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend && pytest tests/test_lock_api.py -v
# Expected: FAIL — router not found
```

- [ ] **Step 3: 实现 LockService**

```python
# backend/app/services/lock_service.py
import redis.asyncio as aioredis
from app.core.config import settings

LOCK_PREFIX = "review_lock:"
LOCK_TTL = 300  # 5 分钟


class LockService:
    def __init__(self):
        self.redis = aioredis.from_url(settings.REDIS_URL)

    async def acquire(self, workorder_id: str, operator_id: str, operator_name: str) -> dict:
        """获取锁。返回 {locked, owner, locked_minutes?}"""
        key = f"{LOCK_PREFIX}{workorder_id}"
        existing = await self.redis.get(key)
        if existing:
            owner_id, owner_name, locked_at = existing.decode().split(":")
            if owner_id == operator_id:
                await self.redis.expire(key, LOCK_TTL)  # 幂等：刷新 TTL
                return {"locked": True, "owner": owner_name}
            else:
                return {"locked": False, "owner": owner_name, "locked_minutes": 3}
        else:
            import datetime
            now = datetime.datetime.utcnow().isoformat()
            value = f"{operator_id}:{operator_name}:{now}"
            await self.redis.set(key, value, ex=LOCK_TTL)
            return {"locked": True, "owner": operator_name}

    async def release(self, workorder_id: str, operator_id: str) -> None:
        """释放锁。仅持有者可释放，否则抛出 PermissionError"""
        key = f"{LOCK_PREFIX}{workorder_id}"
        existing = await self.redis.get(key)
        if not existing:
            return  # 锁已过期，无需操作
        owner_id, _, _ = existing.decode().split(":")
        if owner_id != operator_id:
            raise PermissionError("仅锁持有者可释放")

        await self.redis.delete(key)

    async def heartbeat(self, workorder_id: str, operator_id: str) -> None:
        """心跳续期。仅持有者可续期，否则抛出 LockLostError"""
        key = f"{LOCK_PREFIX}{workorder_id}"
        existing = await self.redis.get(key)
        if not existing:
            raise LockLostError("编辑锁已过期，请刷新页面")
        owner_id, _, _ = existing.decode().split(":")
        if owner_id != operator_id:
            raise LockLostError("编辑锁已被他人获取，请刷新页面")

        await self.redis.expire(key, LOCK_TTL)


class LockLostError(Exception):
    pass
```

- [ ] **Step 4: 实现 Lock Router**

```python
# backend/app/routers/lock.py
from fastapi import APIRouter, Depends, HTTPException
from app.auth.dependencies import get_current_user, CurrentUser
from app.services.lock_service import LockService, LockLostError

router = APIRouter(prefix="/api/workorders", tags=["lock"])


@router.post("/{workorder_id}/lock")
async def acquire_lock(
    workorder_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    service = LockService()
    return await service.acquire(workorder_id, current_user.user_id, current_user.name)


@router.delete("/{workorder_id}/lock")
async def release_lock(
    workorder_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    service = LockService()
    try:
        await service.release(workorder_id, current_user.user_id)
        return {"status": "released"}
    except PermissionError:
        raise HTTPException(status_code=403, detail="仅锁持有者可释放")


@router.put("/{workorder_id}/lock")
async def heartbeat_lock(
    workorder_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    service = LockService()
    try:
        await service.heartbeat(workorder_id, current_user.user_id)
        return {"status": "ok"}
    except LockLostError as e:
        raise HTTPException(status_code=423, detail=str(e))
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd backend && pytest tests/test_lock_api.py -v
# Expected: all PASS
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/lock_service.py backend/app/routers/lock.py backend/tests/test_lock_api.py
git commit -m "feat: add edit lock API with owner-only release and heartbeat"
```

---

### Task 5: AuditService + BadCaseService

**Files:**
- Create: `backend/app/services/audit_service.py`
- Create: `backend/app/services/bad_case_service.py`

**Interfaces:**
- Consumes: `AsyncSession` (SQLAlchemy), `WorkOrderAuditLog` model (Task 1), `BadCaseSample` model (Task 1)
- Produces: `AuditService.batch_create()`, `BadCaseService.batch_create()`

- [ ] **Step 1: 编写测试**

```python
# backend/tests/test_services.py
import pytest
from unittest.mock import AsyncMock, MagicMock, call
from app.services.audit_service import AuditService
from app.services.bad_case_service import BadCaseService
from app.schemas.review import FieldChange

@pytest.mark.asyncio
async def test_audit_service_batch_create():
    db = AsyncMock()
    service = AuditService(db)
    changes = [
        FieldChange(op="replace", path="/problem_category_l1", field_label="问题分类",
                    old_value="数据问题", new_value="工程问题", ai_confidence=0.72),
        FieldChange(op="replace", path="/order_level", field_label="受理单级别",
                    old_value="P3", new_value="P2", ai_confidence=0.88),
    ]
    await service.batch_create(
        workorder_id="WO001",
        session_id="sess-001",
        changes=changes,
        operator_id="agent-001",
        operator_name="张三",
    )
    assert db.add_all.call_count == 1
    # 验证传入了 2 条审计日志
    args = db.add_all.call_args[0][0]
    assert len(args) == 2
    assert args[0].field_path == "/problem_category_l1"
    assert args[1].field_path == "/order_level"

@pytest.mark.asyncio
async def test_bad_case_service_batch_create():
    db = AsyncMock()
    service = BadCaseService(db)
    changes = [
        FieldChange(op="replace", path="/problem_category_l1", field_label="问题分类",
                    old_value="数据问题", new_value="工程问题", ai_confidence=0.72),
    ]
    await service.batch_create(
        workorder_id="WO001",
        audit_log_ids=[1],
        changes=changes,
    )
    assert db.add_all.call_count == 1
    args = db.add_all.call_args[0][0]
    assert len(args) == 1
    assert args[0].ai_value == "数据问题"
    assert args[0].human_value == "工程问题"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend && pytest tests/test_services.py -v
# Expected: FAIL — module not found
```

- [ ] **Step 3: 实现 AuditService**

```python
# backend/app/services/audit_service.py
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import WorkOrderAuditLog
from app.schemas.review import FieldChange


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def batch_create(
        self,
        *,
        workorder_id: str,
        session_id: str,
        changes: list[FieldChange],
        operator_id: str,
        operator_name: str,
        change_type: str = "replace",
    ) -> list[WorkOrderAuditLog]:
        now = datetime.utcnow()
        logs = [
            WorkOrderAuditLog(
                workorder_id=workorder_id,
                session_id=session_id,
                field_path=c.path,
                field_label=c.field_label,
                old_value=str(c.old_value) if c.old_value is not None else None,
                new_value=str(c.new_value) if c.new_value is not None else None,
                change_type=c.op,
                ai_confidence=c.ai_confidence,
                operator_id=operator_id,
                operator_name=operator_name,
                operated_at=now,
            )
            for c in changes
        ]
        self.db.add_all(logs)
        await self.db.flush()
        return logs

    async def create_reject_log(
        self,
        *,
        workorder_id: str,
        session_id: str,
        reject_reason: str,
        operator_id: str,
        operator_name: str,
    ):
        log = WorkOrderAuditLog(
            workorder_id=workorder_id,
            session_id=session_id,
            field_path="/_rejected",
            field_label="退回重填",
            old_value=None,
            new_value=reject_reason,
            change_type="rejected",
            operator_id=operator_id,
            operator_name=operator_name,
            operated_at=datetime.utcnow(),
        )
        self.db.add(log)
        await self.db.flush()
```

- [ ] **Step 4: 实现 BadCaseService**

```python
# backend/app/services/bad_case_service.py
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.bad_case import BadCaseSample
from app.schemas.review import FieldChange


class BadCaseService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def batch_create(
        self,
        *,
        workorder_id: str,
        audit_log_ids: list[int],
        changes: list[FieldChange],
    ):
        now = datetime.utcnow()
        samples = [
            BadCaseSample(
                workorder_id=workorder_id,
                audit_log_id=audit_log_id,
                field_path=c.path,
                ai_value=str(c.old_value) if c.old_value is not None else None,
                human_value=str(c.new_value) if c.new_value is not None else None,
                ai_confidence=c.ai_confidence,
                sample_status="pending",
                source="review_correction",
                created_at=now,
            )
            for c, audit_log_id in zip(changes, audit_log_ids)
        ]
        self.db.add_all(samples)
        await self.db.flush()
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd backend && pytest tests/test_services.py -v
# Expected: all PASS
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/audit_service.py backend/app/services/bad_case_service.py backend/tests/test_services.py
git commit -m "feat: add AuditService and BadCaseService with batch creation"
```

---

### Task 6: ReviewService + Review Router

**Files:**
- Create: `backend/app/services/review_service.py`
- Create: `backend/app/routers/review.py`

**Interfaces:**
- Consumes: `ReviewRequest` (Task 2), `CurrentUser` (Task 3), `AuditService` (Task 5), `BadCaseService` (Task 5), `ALLOWED_FIELDS` (Task 2)
- Produces: `POST /api/workorders/{id}/review`, `GET /api/workorders/{id}/audit-logs`

- [ ] **Step 1: 编写测试**

```python
# backend/tests/test_review_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from app.main import app
from app.auth.dependencies import CurrentUser, get_current_user

@pytest.fixture
def mock_user():
    return CurrentUser(user_id="agent-001", name="张三", role="customer_service_agent", department="售后部")

@pytest.fixture
async def client(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_review_confirm_success(client, mock_user):
    """确认提交：version 匹配 + 有变更 → 写审计日志 + bad_case"""
    with patch("app.services.review_service.ReviewService._execute_confirm") as mock_exec:
        mock_exec.return_value = {"review_id": "rev-001", "workorder_id": "WO001",
                                   "status": "confirmed", "change_count": 2,
                                   "bad_case_count": 2, "next_status": "dispatching"}
        resp = await client.post("/api/workorders/WO001/review", json={
            "session_id": "sess-001",
            "version": 1,
            "changes": [
                {"op": "replace", "path": "/problem_category_l1", "field_label": "问题分类",
                 "old_value": "数据问题", "new_value": "工程问题", "ai_confidence": 0.72},
            ],
            "reject_reason": None,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "confirmed"
        assert data["change_count"] == 2

@pytest.mark.asyncio
async def test_review_reject_success(client):
    """退回重填：不写 bad_case"""
    with patch("app.services.review_service.ReviewService._execute_reject") as mock_exec:
        mock_exec.return_value = {"review_id": "rev-002", "workorder_id": "WO001",
                                   "status": "rejected", "change_count": 0,
                                   "bad_case_count": 0, "next_status": "pending_review"}
        resp = await client.post("/api/workorders/WO001/review", json={
            "session_id": "sess-002",
            "version": 1,
            "changes": [],
            "reject_reason": "分类与客户描述不符",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
        assert data["bad_case_count"] == 0

@pytest.mark.asyncio
async def test_review_version_conflict(client):
    """版本冲突返回 409"""
    with patch("app.services.review_service.ReviewService._execute_confirm") as mock_exec:
        mock_exec.side_effect = HTTPException(status_code=409, detail="版本冲突，请刷新重试")
        resp = await client.post("/api/workorders/WO001/review", json={
            "session_id": "sess-003",
            "version": 1,  # 已过期
            "changes": [],
            "reject_reason": None,
        })
        assert resp.status_code == 409

@pytest.mark.asyncio
async def test_review_field_not_in_whitelist(client):
    """非白名单字段被静默过滤"""
    with patch("app.services.review_service.ReviewService._execute_confirm") as mock_exec:
        mock_exec.return_value = {"review_id": "rev-003", "workorder_id": "WO001",
                                   "status": "confirmed", "change_count": 0,
                                   "bad_case_count": 0, "next_status": "dispatching"}
        resp = await client.post("/api/workorders/WO001/review", json={
            "session_id": "sess-004",
            "version": 1,
            "changes": [
                {"op": "replace", "path": "/created_at", "field_label": "创建时间",
                 "old_value": "2020-01-01", "new_value": "2021-01-01", "ai_confidence": None},
            ],
            "reject_reason": None,
        })
        assert resp.status_code == 200  # 不报错，但 created_at 不会被更新
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend && pytest tests/test_review_api.py -v
# Expected: FAIL — router not found
```

- [ ] **Step 3: 实现 ReviewService**

```python
# backend/app/services/review_service.py
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from fastapi import HTTPException
from app.schemas.review import ReviewRequest, ReviewResponse, ALLOWED_FIELDS
from app.services.audit_service import AuditService
from app.services.bad_case_service import BadCaseService
from app.services.lock_service import LockService


class ReviewService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit_service = AuditService(db)
        self.bad_case_service = BadCaseService(db)
        self.lock_service = LockService()

    async def review(
        self,
        *,
        workorder_id: str,
        request: ReviewRequest,
        operator_id: str,
        operator_name: str,
        operator_department: str,
    ) -> dict:
        # 1. 幂等性检查
        result = await self.db.execute(
            text("SELECT id FROM workorder_audit_log WHERE session_id = :sid LIMIT 1"),
            {"sid": request.session_id},
        )
        if result.scalar():
            return self._build_existing_response(workorder_id, request)

        if request.reject_reason is not None:
            return await self._execute_reject(
                workorder_id, request, operator_id, operator_name
            )
        else:
            return await self._execute_confirm(
                workorder_id, request, operator_id, operator_name, operator_department
            )

    async def _execute_confirm(self, workorder_id, request, operator_id, operator_name, operator_department):
        async with self.db.begin():
            # 2. 乐观锁 UPDATE — confirmed 分支
            result = await self.db.execute(
                text("""
                    UPDATE workorders
                    SET status = 'confirmed', version = version + 1,
                        reviewed_at = :now, reviewed_by = :operator_name
                    WHERE id = :id AND version = :version AND status = 'pending_review'
                """),
                {
                    "id": workorder_id,
                    "version": request.version,
                    "now": datetime.utcnow(),
                    "operator_name": operator_name,
                },
            )
            if result.rowcount == 0:
                raise HTTPException(status_code=409, detail="版本冲突，请刷新重试")

            # 3. 白名单过滤 + 更新变更字段
            filtered_changes = [
                c for c in request.changes
                if c.path.lstrip("/") in ALLOWED_FIELDS
            ]
            for c in filtered_changes:
                field_name = c.path.lstrip("/")
                await self.db.execute(
                    text(f"UPDATE workorders SET {field_name} = :val WHERE id = :id"),
                    {"val": c.new_value, "id": workorder_id},
                )

            # 4. 写入审计日志
            audit_logs = await self.audit_service.batch_create(
                workorder_id=workorder_id,
                session_id=request.session_id,
                changes=filtered_changes,
                operator_id=operator_id,
                operator_name=operator_name,
            )

            # 5. bad_case 回流（仅 confirmed + 有变更时）
            bad_case_count = 0
            if filtered_changes:
                audit_log_ids = [log.id for log in audit_logs]
                await self.bad_case_service.batch_create(
                    workorder_id=workorder_id,
                    audit_log_ids=audit_log_ids,
                    changes=filtered_changes,
                )
                bad_case_count = len(filtered_changes)

            # 6. 释放编辑锁
            await self.lock_service.release(workorder_id, operator_id)

        review_id = f"rev-{uuid.uuid4().hex[:12]}"
        return {
            "review_id": review_id,
            "workorder_id": workorder_id,
            "status": "confirmed",
            "change_count": len(filtered_changes),
            "bad_case_count": bad_case_count,
            "next_status": "dispatching",
        }

    async def _execute_reject(self, workorder_id, request, operator_id, operator_name):
        async with self.db.begin():
            result = await self.db.execute(
                text("""
                    UPDATE workorders
                    SET status = 'pending_review', version = version + 1,
                        reject_count = reject_count + 1,
                        last_reject_reason = :reason,
                        last_rejected_by = :operator_name,
                        last_rejected_at = :now
                    WHERE id = :id AND version = :version AND status = 'pending_review'
                """),
                {
                    "id": workorder_id,
                    "version": request.version,
                    "reason": request.reject_reason,
                    "operator_name": operator_name,
                    "now": datetime.utcnow(),
                },
            )
            if result.rowcount == 0:
                raise HTTPException(status_code=409, detail="版本冲突，请刷新重试")

            await self.audit_service.create_reject_log(
                workorder_id=workorder_id,
                session_id=request.session_id,
                reject_reason=request.reject_reason,
                operator_id=operator_id,
                operator_name=operator_name,
            )

            # 释放锁
            await self.lock_service.release(workorder_id, operator_id)

        review_id = f"rev-{uuid.uuid4().hex[:12]}"
        return {
            "review_id": review_id,
            "workorder_id": workorder_id,
            "status": "rejected",
            "change_count": 0,
            "bad_case_count": 0,
            "next_status": "pending_review",
        }

    def _build_existing_response(self, workorder_id, request):
        return {
            "review_id": "dup",
            "workorder_id": workorder_id,
            "status": "confirmed" if request.reject_reason is None else "rejected",
            "change_count": 0,
            "bad_case_count": 0,
            "next_status": "dispatching",
        }
```

- [ ] **Step 4: 实现 Review Router**

```python
# backend/app/routers/review.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import get_current_user, CurrentUser
from app.schemas.review import ReviewRequest, ReviewResponse, AuditLogEntry
from app.services.review_service import ReviewService
from app.core.database import get_db
from app.models.audit_log import WorkOrderAuditLog
from sqlalchemy import select

router = APIRouter(prefix="/api/workorders", tags=["review"])


@router.post("/{workorder_id}/review", response_model=ReviewResponse)
async def review_workorder(
    workorder_id: str,
    request: ReviewRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ReviewService(db)
    result = await service.review(
        workorder_id=workorder_id,
        request=request,
        operator_id=current_user.user_id,
        operator_name=current_user.name,
        operator_department=current_user.department,
    )
    return ReviewResponse(**result)


@router.get("/{workorder_id}/audit-logs")
async def get_audit_logs(
    workorder_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WorkOrderAuditLog)
        .where(WorkOrderAuditLog.workorder_id == workorder_id)
        .order_by(WorkOrderAuditLog.operated_at.desc())
    )
    rows = result.scalars().all()

    sessions = {}
    for row in rows:
        sid = row.session_id
        if sid not in sessions:
            sessions[sid] = {
                "session_id": sid,
                "operator_name": row.operator_name,
                "operated_at": row.operated_at.isoformat(),
                "changes": [],
            }
        sessions[sid]["changes"].append({
            "op": row.change_type,
            "path": row.field_path,
            "field_label": row.field_label,
            "old_value": row.old_value,
            "new_value": row.new_value,
            "ai_confidence": float(row.ai_confidence) if row.ai_confidence else None,
        })

    return list(sessions.values())
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd backend && pytest tests/test_review_api.py -v
# Expected: all PASS
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/review_service.py backend/app/routers/review.py backend/tests/test_review_api.py
git commit -m "feat: add ReviewService with confirm/reject branches and review router"
```

---

### Task 7: 后端集成测试 — 端到端事务流程

**Files:**
- Create: `backend/tests/test_review_integration.py`

**Interfaces:**
- Consumes: All backend modules from Tasks 1-6

- [ ] **Step 1: 编写端到端测试**

```python
# backend/tests/test_review_integration.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.auth.dependencies import CurrentUser, get_current_user
from app.models.workorder import WorkOrder
from app.models.audit_log import WorkOrderAuditLog
from app.models.bad_case import BadCaseSample

@pytest.fixture
def mock_user():
    return CurrentUser(user_id="agent-001", name="张三", role="customer_service_agent", department="售后部")

@pytest.fixture
async def client(mock_user, test_db):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    # 创建测试工单
    async with test_db.begin():
        wo = WorkOrder(
            id="WO-E2E-001",
            status="pending_review",
            version=1,
            station_name="测试场站",
            project_province="广东",
            problem_description="测试问题描述",
            problem_category_l1="数据问题",
            order_level="P3",
            responsible_person="李燕昆",
            responsible_department="数据中心",
            primary_department="数据中心",
            after_sales_person="李燕昆",
        )
        test_db.add(wo)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_full_confirm_flow(client, test_db):
    """端到端：确认提交 → 工单状态变更 + 审计日志 + bad_case 全部写入"""
    resp = await client.post("/api/workorders/WO-E2E-001/review", json={
        "session_id": "e2e-sess-001",
        "version": 1,
        "changes": [
            {"op": "replace", "path": "/problem_category_l1", "field_label": "问题分类",
             "old_value": "数据问题", "new_value": "工程问题", "ai_confidence": 0.72},
            {"op": "replace", "path": "/order_level", "field_label": "受理单级别",
             "old_value": "P3", "new_value": "P2", "ai_confidence": 0.88},
        ],
        "reject_reason": None,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "confirmed"
    assert data["change_count"] == 2
    assert data["bad_case_count"] == 2

    # 验证工单状态
    result = await test_db.execute(
        "SELECT status, version, reviewed_at, reviewed_by FROM workorders WHERE id = 'WO-E2E-001'"
    )
    row = result.fetchone()
    assert row[0] == "confirmed"
    assert row[1] == 2  # version 自增
    assert row[3] == "张三"

    # 验证审计日志
    result = await test_db.execute(
        "SELECT COUNT(*) FROM workorder_audit_log WHERE workorder_id = 'WO-E2E-001'"
    )
    assert result.scalar() == 2

    # 验证 bad_case
    result = await test_db.execute(
        "SELECT COUNT(*) FROM bad_case_sample WHERE workorder_id = 'WO-E2E-001'"
    )
    assert result.scalar() == 2

@pytest.mark.asyncio
async def test_full_reject_flow_no_bad_case(client, test_db):
    """端到端：退回重填 → 不写 bad_case"""
    # 先创建另一个工单
    async with test_db.begin():
        wo = WorkOrder(
            id="WO-E2E-002", status="pending_review", version=1,
            station_name="测试场站2", project_province="北京",
            problem_description="测试", problem_category_l1="产品问题",
            order_level="P3", responsible_person="朱莉",
            responsible_department="产品部", primary_department="产品部",
            after_sales_person="朱莉",
        )
        test_db.add(wo)

    resp = await client.post("/api/workorders/WO-E2E-002/review", json={
        "session_id": "e2e-sess-002",
        "version": 1,
        "changes": [],
        "reject_reason": "分类不准确需重新判定",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert data["bad_case_count"] == 0

    # 验证 reject_count 自增
    result = await test_db.execute(
        "SELECT reject_count, last_reject_reason FROM workorders WHERE id = 'WO-E2E-002'"
    )
    row = result.fetchone()
    assert row[0] == 1
    assert row[1] == "分类不准确需重新判定"

    # 验证 bad_case 为 0
    result = await test_db.execute(
        "SELECT COUNT(*) FROM bad_case_sample WHERE workorder_id = 'WO-E2E-002'"
    )
    assert result.scalar() == 0

@pytest.mark.asyncio
async def test_idempotency(client):
    """重复提交同一 session_id 返回已有结果"""
    resp1 = await client.post("/api/workorders/WO-E2E-001/review", json={
        "session_id": "e2e-sess-003",
        "version": 2,  # 注意：上一步已更新为 version=2
        "changes": [],
        "reject_reason": None,
    })
    assert resp1.status_code == 200

    resp2 = await client.post("/api/workorders/WO-E2E-001/review", json={
        "session_id": "e2e-sess-003",  # 相同 session_id
        "version": 2,
        "changes": [],
        "reject_reason": None,
    })
    assert resp2.status_code == 200
    # 幂等返回 review_id 为 "dup"
    assert resp2.json()["review_id"] == "dup"
```

- [ ] **Step 2: 运行测试验证通过**

```bash
cd backend && pytest tests/test_review_integration.py -v
# Expected: all PASS
```

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_review_integration.py
git commit -m "test: add end-to-end integration tests for review confirm/reject/idempotency"
```

---

### Task 8: 前端类型定义 + API Client

**Files:**
- Create: `frontend/src/api/review.ts`
- Create: `frontend/src/pages/WorkOrderReview/types.ts`

**Interfaces:**
- Produces: `FieldChange`, `ReviewRequest`, `ReviewResponse`, `WorkOrderData`, `LockStatus`, `submitReview()`, `fetchWorkOrder()`, `acquireLock()`, `releaseLock()`, `heartbeatLock()`, `fetchAuditLogs()`

- [ ] **Step 1: TypeScript 类型定义**

```typescript
// frontend/src/pages/WorkOrderReview/types.ts

export interface FieldChange {
  op: 'replace' | 'add' | 'remove';
  path: string;
  field_label: string;
  old_value: unknown;
  new_value: unknown;
  ai_confidence: number | null;
}

export interface ReviewRequest {
  session_id: string;
  version: number;
  changes: FieldChange[];
  reject_reason: string | null;
}

export interface ReviewResponse {
  review_id: string;
  workorder_id: string;
  status: 'confirmed' | 'rejected';
  change_count: number;
  bad_case_count: number;
  next_status: string;
}

export interface WorkOrderData {
  id: string;
  version: number;
  status: string;
  reject_count: number;
  last_reject_reason: string | null;
  last_rejected_by: string | null;
  last_rejected_at: string | null;
  ai_confidence: number | null;
  // 核心字段
  station_name: string;
  dispatch_name: string;
  project_code: string;
  project_name: string;
  project_province: string;
  customer_name: string;
  problem_description: string;
  feedback_channel: string;
  product_line: string;
  product_category: string;
  product_type: string;
  customer_level: string;
  problem_category_l1: string;
  problem_category_l2: string;
  problem_category_l3: string;
  order_type: string;
  problem_type: string;
  fault_category: string;
  fault_detail: string;
  responsible_person: string;
  responsible_department: string;
  primary_department: string;
  after_sales_person: string;
  transferred_person: string;
  transferred_department: string;
  order_level: string;
  fault_level: string;
  onsite_level: string;
  required_solve_time: string;
  // 只读字段
  serial_number: string;
  created_at: string;
  initiator: string;
  initiator_department: string;
  [key: string]: unknown;
}

export interface LockStatus {
  locked: boolean;
  owner?: string;
  locked_minutes?: number;
}

export interface AuditLogSession {
  session_id: string;
  operator_name: string;
  operated_at: string;
  changes: FieldChange[];
}

export const EXCEPTION_RULES = {
  missing_province: { field: 'project_province', message: '场站省份未填写' },
  missing_category: { field: 'problem_category_l1', message: '问题分类未选择' },
  missing_assignee: { field: 'responsible_person', message: '问题责任人未分配' },
} as const;
```

- [ ] **Step 2: API Client**

```typescript
// frontend/src/api/review.ts
import type {
  WorkOrderData, ReviewRequest, ReviewResponse,
  LockStatus, AuditLogSession,
} from '../pages/WorkOrderReview/types';

const BASE = '/api/workorders';

export async function fetchWorkOrder(id: string): Promise<WorkOrderData> {
  const res = await fetch(`${BASE}/${id}`);
  if (!res.ok) throw new Error(`获取工单失败: ${res.status}`);
  return res.json();
}

export async function submitReview(
  id: string, body: ReviewRequest
): Promise<ReviewResponse> {
  const res = await fetch(`${BASE}/${id}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (res.status === 409) {
    throw new ConflictError((await res.json()).detail);
  }
  if (!res.ok) throw new Error(`提交审查失败: ${res.status}`);
  return res.json();
}

export class ConflictError extends Error {}

export async function acquireLock(id: string): Promise<LockStatus> {
  const res = await fetch(`${BASE}/${id}/lock`, { method: 'POST' });
  if (!res.ok) throw new Error(`获取锁失败: ${res.status}`);
  return res.json();
}

export async function releaseLock(id: string): Promise<void> {
  await fetch(`${BASE}/${id}/lock`, { method: 'DELETE' });
}

export async function heartbeatLock(id: string): Promise<'ok' | 'lost'> {
  const res = await fetch(`${BASE}/${id}/lock`, { method: 'PUT' });
  if (res.status === 423) return 'lost';
  if (!res.ok) throw new Error(`心跳失败: ${res.status}`);
  return 'ok';
}

export async function fetchAuditLogs(id: string): Promise<AuditLogSession[]> {
  const res = await fetch(`${BASE}/${id}/audit-logs`);
  if (!res.ok) throw new Error(`获取审计日志失败: ${res.status}`);
  return res.json();
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/review.ts frontend/src/pages/WorkOrderReview/types.ts
git commit -m "feat: add frontend types and API client for review page"
```

---

### Task 9: Formily Schema + 变更捕获 Hook

**Files:**
- Create: `frontend/src/pages/WorkOrderReview/schema.ts`
- Create: `frontend/src/pages/WorkOrderReview/useChangeTracker.ts`

**Interfaces:**
- Consumes: `WorkOrderData`, `FieldChange` (Task 8)
- Produces: `reviewSchema` (Formily JSON Schema), `useChangeTracker()` hook

- [ ] **Step 1: Formily Schema**

```typescript
// frontend/src/pages/WorkOrderReview/schema.ts
import type { ISchema } from '@formily/react';

export const reviewSchema: ISchema = {
  type: 'object',
  properties: {
    tabGroup: {
      type: 'void',
      'x-component': 'FormTab',
      properties: {
        basicInfo: {
          type: 'object',
          'x-component': 'FormTab.TabPane',
          'x-component-props': { tab: '基本信息' },
          properties: {
            station_name: {
              type: 'string', title: '场站名称', required: true,
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            dispatch_name: {
              type: 'string', title: '调度名称',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            project_code: {
              type: 'string', title: '项目编号',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            project_name: {
              type: 'string', title: '项目名称',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            project_province: {
              type: 'string', title: '项目省份', required: true,
              'x-decorator': 'FormItem', 'x-component': 'Select',
              'x-reactions': ['{{useAsyncProvinceList()}}'],
            },
            customer_name: {
              type: 'string', title: '大客户简称',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            problem_description: {
              type: 'string', title: '问题描述', required: true,
              'x-decorator': 'FormItem',
              'x-component': 'Input.TextArea',
              'x-component-props': { rows: 3 },
            },
            feedback_channel: {
              type: 'string', title: '反馈渠道',
              'x-decorator': 'FormItem', 'x-component': 'Select',
              enum: [
                { label: '400电话', value: '400' },
                { label: '企业微信', value: 'wechat' },
                { label: '邮件', value: 'email' },
                { label: '小程序', value: 'miniapp' },
              ],
            },
            product_line: {
              type: 'string', title: '产品线',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            product_category: {
              type: 'string', title: '产品类别',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            customer_level: {
              type: 'string', title: '客户级别',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
          },
        },
        classification: {
          type: 'object',
          'x-component': 'FormTab.TabPane',
          'x-component-props': { tab: '分类归属' },
          properties: {
            problem_category_l1: {
              type: 'string', title: '问题分类（一级）', required: true,
              'x-decorator': 'FormItem', 'x-component': 'Select',
              enum: [
                { label: '产品问题', value: 'product' },
                { label: '数据问题', value: 'data' },
                { label: '工程问题', value: 'engineering' },
                { label: '采购问题', value: 'procurement' },
                { label: '其他问题', value: 'other' },
              ],
              'x-reactions': [
                {
                  target: 'tabGroup.classification.problem_category_l2',
                  effects: ['onFieldValueChange'],
                  fulfill: { state: { dataSource: '{{useAsyncCategoryL2($self.value)}}' } },
                },
              ],
            },
            problem_category_l2: {
              type: 'string', title: '问题分类（二级）',
              'x-decorator': 'FormItem', 'x-component': 'Select',
              'x-reactions': [
                {
                  target: 'tabGroup.classification.problem_category_l3',
                  effects: ['onFieldValueChange'],
                  fulfill: { state: { dataSource: '{{useAsyncCategoryL3($self.value)}}' } },
                },
              ],
            },
            problem_category_l3: {
              type: 'string', title: '问题分类（三级）',
              'x-decorator': 'FormItem', 'x-component': 'Select',
            },
            order_type: {
              type: 'string', title: '受理单类型',
              'x-decorator': 'FormItem', 'x-component': 'Select',
              enum: [
                { label: '售后单', value: 'normal' },
                { label: 'A类售后单', value: 'a_class' },
                { label: '大客户售后单', value: 'vip' },
              ],
            },
            problem_type: {
              type: 'string', title: '问题类型',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            fault_category: {
              type: 'string', title: '故障分类',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            fault_detail: {
              type: 'string', title: '故障明细',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
          },
        },
        routing: {
          type: 'object',
          'x-component': 'FormTab.TabPane',
          'x-component-props': { tab: '路由分配' },
          properties: {
            responsible_person: {
              type: 'string', title: '问题责任人', required: true,
              'x-decorator': 'FormItem', 'x-component': 'Select',
              'x-reactions': ['{{useAsyncAssignablePerson()}}'],
            },
            responsible_department: {
              type: 'string', title: '责任部门', required: true,
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            primary_department: {
              type: 'string', title: '一级部门',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            after_sales_person: {
              type: 'string', title: '售后责任人',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            transferred_person: {
              type: 'string', title: '移交后责任人',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            transferred_department: {
              type: 'string', title: '移交后部门',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
          },
        },
        priority: {
          type: 'object',
          'x-component': 'FormTab.TabPane',
          'x-component-props': { tab: '时效等级' },
          properties: {
            order_level: {
              type: 'string', title: '受理单级别', required: true,
              'x-decorator': 'FormItem', 'x-component': 'Radio.Group',
              enum: [
                { label: 'P1 紧急', value: 'P1' },
                { label: 'P2 高', value: 'P2' },
                { label: 'P3 中', value: 'P3' },
                { label: 'P4 低', value: 'P4' },
              ],
            },
            fault_level: {
              type: 'string', title: '故障等级',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            onsite_level: {
              type: 'string', title: '进场等级',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            required_solve_time: {
              type: 'string', title: '要求解决时间',
              'x-decorator': 'FormItem', 'x-component': 'DatePicker',
            },
          },
        },
      },
    },
  },
};
```

- [ ] **Step 2: 变更捕获 Hook**

```typescript
// frontend/src/pages/WorkOrderReview/useChangeTracker.ts
import { useRef, useCallback } from 'react';
import { onFieldValueChange, onFormSubmit } from '@formily/core';
import type { Form } from '@formily/core';
import isEqual from 'lodash.isequal';
import type { FieldChange, WorkOrderData } from './types';

export function useChangeTracker(form: Form, initialValues: WorkOrderData) {
  const changesRef = useRef<FieldChange[]>([]);

  const setupTracker = useCallback(() => {
    form.addEffects('changeTracker', () => {
      onFieldValueChange('*', (field: any) => {
        const path = field.path.toString();
        const initialValue = initialValues[path];
        const currentValue = field.value;
        const actuallyChanged = !isEqual(currentValue, initialValue);

        if (field.modified && actuallyChanged) {
          const existing = changesRef.current.findIndex(c => c.path === `/${path}`);
          const change: FieldChange = {
            op: 'replace',
            path: `/${path}`,
            field_label: field.title ?? path,
            old_value: initialValue,
            new_value: currentValue,
            ai_confidence: field.data?.aiConfidence ?? null,
          };
          if (existing >= 0) {
            changesRef.current[existing] = change;
          } else {
            changesRef.current.push(change);
          }
        } else if (field.modified && !actuallyChanged) {
          changesRef.current = changesRef.current.filter(
            c => c.path !== `/${path}`
          );
        }
      });

      onFormSubmit(() => {
        form.setFieldState('__changes__', (state: any) => {
          state.value = changesRef.current;
        });
      });
    });
  }, [form, initialValues]);

  return { changesRef, setupTracker };
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/WorkOrderReview/schema.ts frontend/src/pages/WorkOrderReview/useChangeTracker.ts
git commit -m "feat: add Formily review schema and change tracker hook"
```

---

### Task 10: UI 组件 — AiPreviewPanel + EditFormPanel + ChangePreviewDrawer + ExceptionAlert + WorkOrderHeader

**Files:**
- Create: `frontend/src/pages/WorkOrderReview/AiPreviewPanel.tsx`
- Create: `frontend/src/pages/WorkOrderReview/EditFormPanel.tsx`
- Create: `frontend/src/pages/WorkOrderReview/ChangePreviewDrawer.tsx`
- Create: `frontend/src/pages/WorkOrderReview/ExceptionAlert.tsx`
- Create: `frontend/src/pages/WorkOrderReview/WorkOrderHeader.tsx`

**Interfaces:**
- Consumes: `WorkOrderData`, `FieldChange`, `reviewSchema`, `EXCEPTION_RULES` (Task 8, 9)
- Produces: 5 UI components

- [ ] **Step 1: WorkOrderHeader**

```tsx
// frontend/src/pages/WorkOrderReview/WorkOrderHeader.tsx
import React from 'react';
import { Descriptions, Tag, Space } from 'antd';
import type { WorkOrderData } from './types';

interface Props {
  workorder: WorkOrderData;
}

export const WorkOrderHeader: React.FC<Props> = ({ workorder }) => (
  <div style={{ marginBottom: 16 }}>
    <Space style={{ marginBottom: 8 }}>
      <Tag color="blue">待审查</Tag>
      {workorder.ai_confidence != null && workorder.ai_confidence < 0.8 && (
        <Tag color="red">AI 低置信度</Tag>
      )}
    </Space>
    <Descriptions size="small" column={4}>
      <Descriptions.Item label="流水号">{workorder.serial_number}</Descriptions.Item>
      <Descriptions.Item label="发起时间">{workorder.created_at}</Descriptions.Item>
      <Descriptions.Item label="发起人">{workorder.initiator}</Descriptions.Item>
      <Descriptions.Item label="发起部门">{workorder.initiator_department}</Descriptions.Item>
      <Descriptions.Item label="AI 置信度">
        {workorder.ai_confidence != null
          ? `${(workorder.ai_confidence * 100).toFixed(0)}%`
          : '-'}
      </Descriptions.Item>
      <Descriptions.Item label="受理单状态">{workorder.status}</Descriptions.Item>
    </Descriptions>
    {workorder.reject_count > 0 && (
      <div style={{ background: '#fff7e6', padding: '8px 12px', borderRadius: 4, marginTop: 8 }}>
        此工单已被退回 {workorder.reject_count} 次，上次退回原因：
        {workorder.last_reject_reason}（{workorder.last_rejected_by}，{workorder.last_rejected_at}）
      </div>
    )}
  </div>
);
```

- [ ] **Step 2: ExceptionAlert**

```tsx
// frontend/src/pages/WorkOrderReview/ExceptionAlert.tsx
import React from 'react';
import { Alert } from 'antd';
import { EXCEPTION_RULES } from './types';

interface Props {
  exceptions: string[];
}

export const ExceptionAlert: React.FC<Props> = ({ exceptions }) => {
  if (exceptions.length === 0) return null;

  const messages = exceptions.map(key => {
    const rule = EXCEPTION_RULES[key as keyof typeof EXCEPTION_RULES];
    return rule ? rule.message : key;
  });

  return (
    <Alert
      type="warning"
      showIcon
      message="异常提醒：以下信息需要修正后才能提交"
      description={
        <ul style={{ margin: 0, paddingLeft: 20 }}>
          {messages.map((msg, i) => <li key={i}>{msg}</li>)}
        </ul>
      }
      style={{ marginBottom: 16 }}
    />
  );
};
```

- [ ] **Step 3: AiPreviewPanel**

```tsx
// frontend/src/pages/WorkOrderReview/AiPreviewPanel.tsx
import React from 'react';
import { Card, Descriptions, Tag } from 'antd';
import type { WorkOrderData } from './types';

interface Props {
  workorder: WorkOrderData;
}

const FIELD_GROUPS = [
  {
    title: '基本信息',
    fields: [
      ['station_name', '场站名称'],
      ['dispatch_name', '调度名称'],
      ['project_code', '项目编号'],
      ['project_name', '项目名称'],
      ['project_province', '项目省份'],
      ['customer_name', '大客户简称'],
      ['problem_description', '问题描述'],
      ['feedback_channel', '反馈渠道'],
    ],
  },
  {
    title: '分类归属',
    fields: [
      ['problem_category_l1', '一级分类'],
      ['problem_category_l2', '二级分类'],
      ['problem_category_l3', '三级分类'],
      ['order_type', '受理单类型'],
      ['problem_type', '问题类型'],
    ],
  },
  {
    title: '路由分配',
    fields: [
      ['responsible_person', '问题责任人'],
      ['responsible_department', '责任部门'],
      ['primary_department', '一级部门'],
      ['after_sales_person', '售后责任人'],
    ],
  },
  {
    title: '时效等级',
    fields: [
      ['order_level', '受理单级别'],
      ['fault_level', '故障等级'],
      ['required_solve_time', '要求解决时间'],
    ],
  },
];

export const AiPreviewPanel: React.FC<Props> = ({ workorder }) => (
  <div>
    {FIELD_GROUPS.map(group => (
      <Card key={group.title} title={group.title} size="small" style={{ marginBottom: 12 }}>
        <Descriptions size="small" column={1}>
          {group.fields.map(([key, label]) => {
            const value = (workorder as any)[key];
            const confKey = `ai_confidence_${key}`;
            const confidence = (workorder as any)[confKey];
            return (
              <Descriptions.Item key={key} label={label}>
                <Tag color="default">AI: {value ?? '-'}</Tag>
                {confidence != null && confidence < 0.8 && (
                  <Tag color="red">{(confidence * 100).toFixed(0)}%</Tag>
                )}
              </Descriptions.Item>
            );
          })}
        </Descriptions>
      </Card>
    ))}
  </div>
);
```

- [ ] **Step 4: EditFormPanel**

```tsx
// frontend/src/pages/WorkOrderReview/EditFormPanel.tsx
import React from 'react';
import { createForm } from '@formily/core';
import { createSchemaField } from '@formily/react';
import { Form, FormItem, Input, Select, DatePicker, Radio, FormTab } from '@formily/antd';
import { reviewSchema } from './schema';
import type { WorkOrderData } from './types';

const SchemaField = createSchemaField({
  components: { FormItem, Input, Select, DatePicker, Radio, FormTab },
});

interface Props {
  workorder: WorkOrderData;
  onFormReady: (form: ReturnType<typeof createForm>) => void;
}

export const EditFormPanel: React.FC<Props> = ({ workorder, onFormReady }) => {
  const form = React.useMemo(() => createForm({
    initialValues: workorder,
    values: workorder,
  }), [workorder]);

  React.useEffect(() => {
    onFormReady(form);
  }, [form, onFormReady]);

  return (
    <Form form={form} layout="vertical">
      <SchemaField schema={reviewSchema} />
    </Form>
  );
};
```

- [ ] **Step 5: ChangePreviewDrawer**

```tsx
// frontend/src/pages/WorkOrderReview/ChangePreviewDrawer.tsx
import React from 'react';
import { Drawer, List, Tag, Button, Space, Empty } from 'antd';
import { ArrowRightOutlined } from '@ant-design/icons';
import type { FieldChange } from './types';

interface Props {
  open: boolean;
  changes: FieldChange[];
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}

export const ChangePreviewDrawer: React.FC<Props> = ({
  open, changes, onConfirm, onCancel, loading,
}) => (
  <Drawer
    title={`变更预览 (${changes.length} 个字段已修改)`}
    open={open}
    onClose={onCancel}
    footer={
      <Space style={{ float: 'right' }}>
        <Button onClick={onCancel}>取消</Button>
        <Button type="primary" onClick={onConfirm} loading={loading}>
          确认提交
        </Button>
      </Space>
    }
  >
    {changes.length === 0 ? (
      <Empty description="未修改任何字段，确认提交" />
    ) : (
      <List
        dataSource={changes}
        renderItem={(item: FieldChange) => (
          <List.Item>
            <div style={{ width: '100%' }}>
              <div style={{ fontWeight: 500, marginBottom: 8 }}>{item.field_label}</div>
              <Space>
                <Tag color="default">AI: {String(item.old_value ?? '-')}</Tag>
                <ArrowRightOutlined />
                <Tag color="orange">修正: {String(item.new_value ?? '-')}</Tag>
              </Space>
              {item.ai_confidence != null && (
                <div style={{ marginTop: 4, color: '#888', fontSize: 12 }}>
                  AI 置信度: {(item.ai_confidence * 100).toFixed(0)}%
                </div>
              )}
            </div>
          </List.Item>
        )}
      />
    )}
  </Drawer>
);
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/WorkOrderReview/
git commit -m "feat: add review UI components — header, preview panel, form panel, drawer, alert"
```

---

### Task 11: WorkOrderReviewPage 组装 + 审查锁定 Hook

**Files:**
- Create: `frontend/src/pages/WorkOrderReview/index.tsx`
- Create: `frontend/src/pages/WorkOrderReview/useReviewLock.ts`

**Interfaces:**
- Consumes: All Task 8-10 modules
- Produces: `WorkOrderReviewPage` (完整审查页), `useReviewLock()` hook

- [ ] **Step 1: useReviewLock Hook**

```typescript
// frontend/src/pages/WorkOrderReview/useReviewLock.ts
import { useEffect, useRef, useCallback } from 'react';
import { message } from 'antd';
import { acquireLock, releaseLock, heartbeatLock } from '../../api/review';
import type { LockStatus } from './types';

const HEARTBEAT_INTERVAL = 2 * 60 * 1000; // 2 分钟

export function useReviewLock(workorderId: string) {
  const lockStatusRef = useRef<LockStatus | null>(null);
  const heartbeatTimerRef = useRef<number | null>(null);

  const tryAcquire = useCallback(async (): Promise<LockStatus> => {
    const status = await acquireLock(workorderId);
    lockStatusRef.current = status;
    if (status.locked) {
      heartbeatTimerRef.current = window.setInterval(async () => {
        const result = await heartbeatLock(workorderId);
        if (result === 'lost') {
          message.error('编辑锁已丢失，请刷新页面', 0);
          clearInterval(heartbeatTimerRef.current!);
        }
      }, HEARTBEAT_INTERVAL);
    }
    return status;
  }, [workorderId]);

  const tryRelease = useCallback(async () => {
    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current);
    }
    try {
      await releaseLock(workorderId);
    } catch {
      // 锁可能已过期，忽略
    }
  }, [workorderId]);

  useEffect(() => {
    return () => {
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
    };
  }, []);

  // 页面关闭时释放锁
  useEffect(() => {
    const handleBeforeUnload = () => {
      releaseLock(workorderId);
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [workorderId]);

  return { lockStatusRef, tryAcquire, tryRelease };
}
```

- [ ] **Step 2: WorkOrderReviewPage 组装**

```tsx
// frontend/src/pages/WorkOrderReview/index.tsx
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Row, Col, Button, Space, message, Spin, Alert } from 'antd';
import type { Form } from '@formily/core';
import { WorkOrderHeader } from './WorkOrderHeader';
import { AiPreviewPanel } from './AiPreviewPanel';
import { EditFormPanel } from './EditFormPanel';
import { ChangePreviewDrawer } from './ChangePreviewDrawer';
import { ExceptionAlert } from './ExceptionAlert';
import { useChangeTracker } from './useChangeTracker';
import { useReviewLock } from './useReviewLock';
import { fetchWorkOrder, submitReview, ConflictError } from '../../api/review';
import type { WorkOrderData, FieldChange, ReviewResponse } from './types';
import { EXCEPTION_RULES } from './types';

export const WorkOrderReviewPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [workorder, setWorkorder] = useState<WorkOrderData | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [changes, setChanges] = useState<FieldChange[]>([]);
  const [exceptions, setExceptions] = useState<string[]>([]);
  const [form, setForm] = useState<Form | null>(null);
  const [lockedByOther, setLockedByOther] = useState(false);
  const [lockOwner, setLockOwner] = useState('');
  const [error, setError] = useState<string | null>(null);

  const sessionIdRef = React.useRef(crypto.randomUUID());
  const { tryAcquire, tryRelease } = useReviewLock(id!);

  // 加载工单 + 获取锁
  useEffect(() => {
    (async () => {
      try {
        const wo = await fetchWorkOrder(id!);
        setWorkorder(wo);

        const lockStatus = await tryAcquire();
        if (!lockStatus.locked) {
          setLockedByOther(true);
          setLockOwner(lockStatus.owner ?? '未知');
        }
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  // 设置变更追踪
  useEffect(() => {
    if (form && workorder) {
      const { changesRef, setupTracker } = useChangeTracker(form, workorder);
      setupTracker();
      // 将 changesRef 同步到 state
      const syncInterval = setInterval(() => {
        setChanges([...changesRef.current]);
      }, 500);
      return () => clearInterval(syncInterval);
    }
  }, [form, workorder]);

  // 实时异常检查
  const checkExceptions = useCallback((wo: WorkOrderData) => {
    const result: string[] = [];
    if (!wo.project_province) result.push('missing_province');
    if (!wo.problem_category_l1) result.push('missing_category');
    if (!wo.responsible_person) result.push('missing_assignee');
    setExceptions(result);
    return result;
  }, []);

  // 提交
  const handleSubmit = useCallback(async () => {
    if (!workorder || !form) return;
    setSubmitting(true);
    try {
      const currentValues = form.values;
      checkExceptions(currentValues as WorkOrderData);

      const resp: ReviewResponse = await submitReview(id!, {
        session_id: sessionIdRef.current,
        version: workorder.version,
        changes,
        reject_reason: null,
      });

      await tryRelease();
      message.success('审查完成');
      navigate('/workorders');
    } catch (e: any) {
      if (e instanceof ConflictError) {
        message.warning(e.message);
      } else {
        setError('提交失败，请重试');
        setDrawerOpen(false);
      }
    } finally {
      setSubmitting(false);
    }
  }, [workorder, form, changes, id, checkExceptions]);

  // 退回重填
  const handleReject = useCallback(async () => {
    const reason = window.prompt('请输入退回原因：');
    if (!reason) return;
    setSubmitting(true);
    try {
      await submitReview(id!, {
        session_id: crypto.randomUUID(),
        version: workorder!.version,
        changes: [],
        reject_reason: reason,
      });
      await tryRelease();
      message.success('已退回重填');
      navigate('/workorders');
    } catch (e: any) {
      if (e instanceof ConflictError) {
        message.warning(e.message);
      } else {
        message.error('退回失败，请重试');
      }
    } finally {
      setSubmitting(false);
    }
  }, [workorder, id]);

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (error) return <Alert type="error" message={error} />;
  if (!workorder) return <Alert type="error" message="工单不存在" />;

  return (
    <div style={{ padding: 24, maxWidth: 1400, margin: '0 auto' }}>
      <WorkOrderHeader workorder={workorder} />

      {lockedByOther && (
        <Alert
          type="info"
          message={`工单正由 ${lockOwner} 审查中，当前为只读模式`}
          style={{ marginBottom: 16 }}
        />
      )}

      <ExceptionAlert exceptions={exceptions} />

      <Row gutter={16}>
        <Col span={12}>
          <AiPreviewPanel workorder={workorder} />
        </Col>
        <Col span={12}>
          <EditFormPanel
            workorder={workorder}
            onFormReady={(f) => {
              setForm(f);
              // 绑定异常检查
              f.addEffects('exceptionCheck', () => {
                f.subscribe((store) => {
                  checkExceptions(store.values as WorkOrderData);
                });
              });
            }}
          />
        </Col>
      </Row>

      <div style={{ textAlign: 'center', marginTop: 24 }}>
        <Space>
          <Button
            type="primary"
            size="large"
            disabled={exceptions.length > 0 || lockedByOther}
            onClick={() => setDrawerOpen(true)}
          >
            确认提交
          </Button>
          <Button
            size="large"
            disabled={lockedByOther}
            onClick={handleReject}
          >
            退回重填
          </Button>
        </Space>
      </div>

      <ChangePreviewDrawer
        open={drawerOpen}
        changes={changes}
        onConfirm={handleSubmit}
        onCancel={() => setDrawerOpen(false)}
        loading={submitting}
      />
    </div>
  );
};

export default WorkOrderReviewPage;
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/WorkOrderReview/index.tsx frontend/src/pages/WorkOrderReview/useReviewLock.ts
git commit -m "feat: compose WorkOrderReviewPage with lock, change tracking, and full flow"
```

---

### Task 12: 前端集成测试

**Files:**
- Create: `frontend/tests/WorkOrderReview.test.tsx`

**Interfaces:**
- Consumes: All frontend modules from Tasks 8-11

- [ ] **Step 1: 编写集成测试**

```tsx
// frontend/tests/WorkOrderReview.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { WorkOrderReviewPage } from '../src/pages/WorkOrderReview';
import * as api from '../src/api/review';

vi.mock('../src/api/review');
vi.mock('react-router-dom', () => ({
  useParams: () => ({ id: 'WO001' }),
  useNavigate: () => vi.fn(),
}));

const mockWorkorder = {
  id: 'WO001',
  version: 1,
  status: 'pending_review',
  reject_count: 0,
  last_reject_reason: null,
  last_rejected_by: null,
  last_rejected_at: null,
  ai_confidence: 0.85,
  serial_number: 'SN20260716001',
  created_at: '2026-07-16T10:00:00Z',
  initiator: '客户A',
  initiator_department: '工程部',
  station_name: '测试场站',
  project_province: '广东',
  problem_description: '功率预测偏差大',
  problem_category_l1: 'data',
  order_level: 'P3',
  responsible_person: '李燕昆',
  responsible_department: '数据中心',
  primary_department: '数据中心',
  after_sales_person: '李燕昆',
  // ... 其余字段省略
};

describe('WorkOrderReviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchWorkOrder as any).mockResolvedValue(mockWorkorder);
    (api.acquireLock as any).mockResolvedValue({ locked: true, owner: '张三' });
  });

  it('shows exception alert when province is missing', async () => {
    const woNoProvince = { ...mockWorkorder, project_province: '' };
    (api.fetchWorkOrder as any).mockResolvedValue(woNoProvince);

    render(<WorkOrderReviewPage />);
    await waitFor(() => {
      expect(screen.getByText(/场站省份未填写/)).toBeInTheDocument();
    });
  });

  it('submit button is disabled when exceptions exist', async () => {
    const woNoCategory = { ...mockWorkorder, problem_category_l1: '' };
    (api.fetchWorkOrder as any).mockResolvedValue(woNoCategory);

    render(<WorkOrderReviewPage />);
    await waitFor(() => {
      const submitBtn = screen.getByText('确认提交');
      expect(submitBtn).toBeDisabled();
    });
  });

  it('shows locked banner when another user holds the lock', async () => {
    (api.acquireLock as any).mockResolvedValue({
      locked: false, owner: '李四', locked_minutes: 3,
    });

    render(<WorkOrderReviewPage />);
    await waitFor(() => {
      expect(screen.getByText(/工单正由 李四 审查中/)).toBeInTheDocument();
    });
  });

  it('shows reject history banner when workorder was rejected before', async () => {
    const woRejected = {
      ...mockWorkorder,
      reject_count: 2,
      last_reject_reason: '分类不准确',
      last_rejected_by: '主管',
      last_rejected_at: '2026-07-16T09:00:00Z',
    };
    (api.fetchWorkOrder as any).mockResolvedValue(woRejected);

    render(<WorkOrderReviewPage />);
    await waitFor(() => {
      expect(screen.getByText(/此工单已被退回 2 次/)).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: 运行测试验证通过**

```bash
cd frontend && npx vitest run tests/WorkOrderReview.test.tsx
# Expected: all PASS
```

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/WorkOrderReview.test.tsx
git commit -m "test: add frontend integration tests for review page"
```

---

## 任务依赖关系

```
Task 1 (DB Models)
  └─→ Task 5 (AuditService + BadCaseService)
        └─→ Task 6 (ReviewService + Router)
              └─→ Task 7 (Backend Integration Tests)

Task 2 (Pydantic Schemas)
  └─→ Task 5, Task 6

Task 3 (Auth Dependency)
  └─→ Task 4 (Lock API), Task 6 (Review Router)

Task 8 (Frontend Types + API Client)
  └─→ Task 9 (Schema + Change Tracker), Task 10 (UI Components), Task 11 (Page Assembly)

Task 9 ──→ Task 11
Task 10 ──→ Task 11
Task 11 ──→ Task 12 (Frontend Integration Tests)
```

## 文件清单

| 文件 | 任务 | 操作 |
|---|---|---|
| `backend/alembic/versions/001_add_review_tables.py` | T1 | Create |
| `backend/app/models/audit_log.py` | T1 | Create |
| `backend/app/models/bad_case.py` | T1 | Create |
| `backend/app/models/workorder.py` | T1 | Modify |
| `backend/app/schemas/review.py` | T2 | Create |
| `backend/tests/test_schemas.py` | T2 | Create |
| `backend/app/auth/dependencies.py` | T3 | Create |
| `backend/tests/test_auth.py` | T3 | Create |
| `backend/app/services/lock_service.py` | T4 | Create |
| `backend/app/routers/lock.py` | T4 | Create |
| `backend/tests/test_lock_api.py` | T4 | Create |
| `backend/app/services/audit_service.py` | T5 | Create |
| `backend/app/services/bad_case_service.py` | T5 | Create |
| `backend/tests/test_services.py` | T5 | Create |
| `backend/app/services/review_service.py` | T6 | Create |
| `backend/app/routers/review.py` | T6 | Create |
| `backend/tests/test_review_api.py` | T6 | Create |
| `backend/tests/test_review_integration.py` | T7 | Create |
| `frontend/src/api/review.ts` | T8 | Create |
| `frontend/src/pages/WorkOrderReview/types.ts` | T8 | Create |
| `frontend/src/pages/WorkOrderReview/schema.ts` | T9 | Create |
| `frontend/src/pages/WorkOrderReview/useChangeTracker.ts` | T9 | Create |
| `frontend/src/pages/WorkOrderReview/AiPreviewPanel.tsx` | T10 | Create |
| `frontend/src/pages/WorkOrderReview/EditFormPanel.tsx` | T10 | Create |
| `frontend/src/pages/WorkOrderReview/ChangePreviewDrawer.tsx` | T10 | Create |
| `frontend/src/pages/WorkOrderReview/ExceptionAlert.tsx` | T10 | Create |
| `frontend/src/pages/WorkOrderReview/WorkOrderHeader.tsx` | T10 | Create |
| `frontend/src/pages/WorkOrderReview/index.tsx` | T11 | Create |
| `frontend/src/pages/WorkOrderReview/useReviewLock.ts` | T11 | Create |
| `frontend/tests/WorkOrderReview.test.tsx` | T12 | Create |