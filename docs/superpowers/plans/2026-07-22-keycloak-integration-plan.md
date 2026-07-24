# Keycloak 统一认证接入 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 shouhou-gongdan 从占位 HS256 JWT 认证替换为 Keycloak OIDC RS256 + 角色鉴权（agent_admin / agent_manager / agent_user），前端接入 authorization_code + PKCE 流程。

**Architecture:** 后端替换 auth 模块为 RS256 JWKS 校验 + 角色依赖注入，前端引入 keycloak-js 自封装 Provider/Hook，配置全部环境变量注入。

**Tech Stack:** FastAPI, PyJWT 2.10, keycloak-js 26, React 18, TypeScript, Vite

## Global Constraints

- 角色编码: agent_admin / agent_manager / agent_user（不可自定义）
- 用户唯一标识: sub（不可使用 username/email）
- 角色读取路径: `resource_access.shouhou-gongdan-api.roles`
- 前端不可配置 client_secret
- JWT 必须校验签名、iss、exp、aud
- admin 接口仅 agent_admin，业务接口三角色均可
- 所有配置通过环境变量注入，不硬编码

---

### Task 1: 后端 — 安装 cryptography 依赖

**Files:**
- Modify: `backend/requirements.txt`

**Interfaces:**
- Produces: `cryptography` 包可用，供 PyJWT RS256 验签使用

- [ ] **Step 1: 添加 cryptography 依赖**

```
PyJWT==2.10.1
cryptography==44.0.0
```

在 `backend/requirements.txt` 中，将 `PyJWT==2.10.1` 行替换为以上两行。

- [ ] **Step 2: 安装依赖**

```bash
cd backend && pip install cryptography==44.0.0
```

- [ ] **Step 3: 验证安装**

```bash
python -c "from cryptography.hazmat.primitives.asymmetric import rsa; print('cryptography OK')"
python -c "import jwt; print('PyJWT OK')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add cryptography for RS256 JWT verification"
```

---

### Task 2: 后端 — 新增 Keycloak 配置项，移除 JWT_SECRET

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`

**Interfaces:**
- Produces: `settings.KEYCLOAK_ISSUER: str`, `settings.KEYCLOAK_JWKS_URL: str`, `settings.KEYCLOAK_AUDIENCE: str`
- Removes: `settings.JWT_SECRET` 及其 validator

- [ ] **Step 1: 修改 `backend/app/core/config.py`**

将当前文件内容替换为：

```python
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Keycloak OIDC
    KEYCLOAK_ISSUER: str = ""
    KEYCLOAK_JWKS_URL: str = ""
    KEYCLOAK_AUDIENCE: str = ""

    REDIS_URL: str = "redis://localhost:6379/0"
    DATABASE_URL: str = ""

    # 销售易（XiaoShouYi）服务工单接口
    XIAOSHOUYI_BASE_URL: str = ""
    XIAOSHOUYI_API_KEY: str = ""


settings = Settings()
```

- [ ] **Step 2: 修改 `backend/.env.example`**

替换内容为：

```env
# 开发环境配置模板
# 复制此文件为 .env 并根据需要修改
# cp .env.example .env

# 数据库连接（docker compose up -d 启动 PostgreSQL）
DATABASE_URL=postgresql+asyncpg://postgres:<DB_PASSWORD>@localhost:5432/shouhou_gongdan

# Keycloak OIDC 认证
KEYCLOAK_ISSUER=http://10.8.6.32:18080/realms/company-dev
KEYCLOAK_JWKS_URL=http://10.8.6.32:18080/realms/company-dev/protocol/openid-connect/certs
KEYCLOAK_AUDIENCE=shouhou-gongdan-api

# Redis 连接（docker compose up -d 启动 Redis）
REDIS_URL=redis://localhost:6379/0

# 销售易 CRM 对接（可选，未配置时跳过同步）
# XIAOSHOUYI_BASE_URL=
# XIAOSHOUYI_API_KEY=
```

- [ ] **Step 3: 验证配置加载**

```bash
cd backend && python -c "
from app.core.config import settings
print('KEYCLOAK_ISSUER:', settings.KEYCLOAK_ISSUER or '(not set - will use .env)')
print('KEYCLOAK_JWKS_URL:', settings.KEYCLOAK_JWKS_URL or '(not set - will use .env)')
print('KEYCLOAK_AUDIENCE:', settings.KEYCLOAK_AUDIENCE or '(not set - will use .env)')
print('OK')
"
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/config.py backend/.env.example
git commit -m "feat: replace JWT_SECRET with Keycloak OIDC config (issuer, jwks_url, audience)"
```

---

### Task 3: 后端 — 新增 CurrentUser schema

**Files:**
- Create: `backend/app/auth/schemas.py`

**Interfaces:**
- Produces: `CurrentUser` dataclass (user_id, username, display_name, email, department_code, department_name, roles: list[str])

- [ ] **Step 1: 创建 `backend/app/auth/schemas.py`**

```python
from dataclasses import dataclass


@dataclass
class CurrentUser:
    """从 Keycloak JWT claims 解析的用户信息。

    user_id 是 sub claim，作为业务系统用户唯一主键。
    roles 来自 resource_access.shouhou-gongdan-api.roles。
    """
    user_id: str
    username: str
    display_name: str
    email: str
    department_code: str
    department_name: str
    roles: list[str]
```

- [ ] **Step 2: 验证模块可导入**

```bash
cd backend && python -c "from app.auth.schemas import CurrentUser; u = CurrentUser('sub-1', 'u1', 'User 1', 'u1@test.com', 'IT', '信息技术部', ['agent_admin']); print(u)"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/auth/schemas.py
git commit -m "feat: add CurrentUser schema with Keycloak claim fields"
```

---

### Task 4: 后端 — 新增 JWT 解码模块 (RS256 + JWKS)

**Files:**
- Create: `backend/app/auth/jwt.py`

**Interfaces:**
- Produces: `async def decode_jwt(token: str) -> dict` — 解码并校验 Keycloak JWT，返回 claims dict
- Consumes: `settings.KEYCLOAK_ISSUER`, `settings.KEYCLOAK_JWKS_URL`, `settings.KEYCLOAK_AUDIENCE`

- [ ] **Step 1: 创建 `backend/app/auth/jwt.py`**

```python
import logging
from functools import lru_cache

import jwt
from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)

# PyJWKClient 内置 LRU 缓存，自动处理 JWKS 获取和刷新
_jwks_client: jwt.PyJWKClient | None = None


def _get_jwks_client() -> jwt.PyJWKClient:
    """获取 JWKS 客户端单例（懒初始化）。"""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(
            uri=settings.KEYCLOAK_JWKS_URL,
            cache_keys=True,
            lifespan=3600,  # 缓存 1 小时
        )
    return _jwks_client


async def decode_jwt(token: str) -> dict:
    """校验 Keycloak JWT 并返回 claims。

    校验项：
    1. RS256 签名（通过 JWKS 公钥）
    2. iss = KEYCLOAK_ISSUER
    3. exp 未过期（pyjwt 自动校验）
    4. aud 包含 KEYCLOAK_AUDIENCE

    Raises:
        HTTPException(401): token 无效或校验失败
    """
    if not settings.KEYCLOAK_JWKS_URL:
        raise HTTPException(
            status_code=500,
            detail="KEYCLOAK_JWKS_URL 未配置",
        )

    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
    except jwt.PyJWKClientError as e:
        logger.warning("JWKS 获取签名密钥失败: %s", e)
        raise HTTPException(status_code=401, detail="无法验证令牌签名") from e

    try:
        payload = jwt.decode(
            token,
            key=signing_key.key,
            algorithms=["RS256"],
            issuer=settings.KEYCLOAK_ISSUER or None,
            audience=settings.KEYCLOAK_AUDIENCE or None,
            options={
                "verify_signature": True,
                "verify_exp": True,
            },
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="认证令牌已过期")
    except jwt.InvalidIssuerError:
        raise HTTPException(
            status_code=401,
            detail=f"无效的令牌签发者，期望 {settings.KEYCLOAK_ISSUER}",
        )
    except jwt.InvalidAudienceError:
        raise HTTPException(
            status_code=401,
            detail=f"无效的令牌受众，期望 {settings.KEYCLOAK_AUDIENCE}",
        )
    except jwt.InvalidTokenError as e:
        logger.warning("JWT 校验失败: %s", e)
        raise HTTPException(status_code=401, detail=f"无效的认证令牌: {e}") from e

    return payload


@lru_cache(maxsize=1)
def get_jwks_client_for_test() -> jwt.PyJWKClient:
    """测试用：获取 JWKS 客户端（可用于依赖覆盖）。"""
    return _get_jwks_client()
```

- [ ] **Step 2: 验证模块可导入**

```bash
cd backend && python -c "from app.auth.jwt import decode_jwt; print('jwt module OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/auth/jwt.py
git commit -m "feat: add RS256 JWT decoder with JWKS validation"
```

---

### Task 5: 后端 — 重写 auth dependencies

**Files:**
- Modify: `backend/app/auth/dependencies.py`

**Interfaces:**
- Produces: `get_current_user` (Depends), `require_admin` (Depends), `require_any_role` (Depends)
- Consumes: `decode_jwt` from `app.auth.jwt`, `CurrentUser` from `app.auth.schemas`
- Removes: 旧 `validate_token`、旧 `decode_jwt`、旧 `CurrentUser`

- [ ] **Step 1: 重写 `backend/app/auth/dependencies.py`**

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.auth.jwt import decode_jwt
from app.auth.schemas import CurrentUser

security = HTTPBearer()

VALID_ROLES = {"agent_admin", "agent_manager", "agent_user"}


def _extract_roles(payload: dict) -> list[str]:
    """从 resource_access.shouhou-gongdan-api.roles 提取角色列表。"""
    try:
        return payload.get("resource_access", {}).get("shouhou-gongdan-api", {}).get("roles", [])
    except (AttributeError, KeyError):
        return []


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    """从 Bearer token 解析当前用户。"""
    token = credentials.credentials
    payload = await decode_jwt(token)

    roles = _extract_roles(payload)

    return CurrentUser(
        user_id=payload.get("sub", ""),
        username=payload.get("preferred_username", ""),
        display_name=payload.get("name", ""),
        email=payload.get("email", ""),
        department_code=payload.get("department_code", ""),
        department_name=payload.get("department_name", ""),
        roles=roles,
    )


async def require_admin(
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """要求 agent_admin 角色。"""
    if "agent_admin" not in user.roles:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


async def require_any_role(
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """要求至少拥有三个有效角色之一。"""
    if not (VALID_ROLES & set(user.roles)):
        raise HTTPException(status_code=403, detail="无有效角色")
    return user
```

- [ ] **Step 2: 验证导入**

```bash
cd backend && python -c "
from app.auth.dependencies import get_current_user, require_admin, require_any_role
print('dependencies OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/auth/dependencies.py
git commit -m "feat: rewrite auth dependencies with Keycloak claims and role checks"
```

---

### Task 6: 后端 — 更新 Router 中的 CurrentUser 字段引用和角色依赖

**Files:**
- Modify: `backend/app/routers/review.py`

**Interfaces:**
- Consumes: `get_current_user`, `require_admin`, `require_any_role` from `app.auth.dependencies`
- Changes: `current_user.name` → `current_user.display_name`, `current_user.department` → `current_user.department_code`

- [ ] **Step 1: 更新 import**

在 `backend/app/routers/review.py` 第 6 行，将：

```python
from app.auth.dependencies import get_current_user, CurrentUser
```

替换为：

```python
from app.auth.dependencies import get_current_user, require_admin, require_any_role
```

- [ ] **Step 2: 更新业务端点 — 添加 require_any_role**

对以下 7 个端点，将 `current_user: CurrentUser = Depends(get_current_user)` 替换为 `current_user: CurrentUser = Depends(require_any_role)`：

| 行号范围 | 端点 |
|----------|------|
| 25-27 | `list_workorders` |
| 45-47 | `get_workorder` |
| 59-61 | `review_workorder` |
| 85-89 | `confirm_workorder` |
| 121-125 | `stash_workorder` |
| 170-173 | `get_stash` |
| 191-194 | `delete_stash` |
| 209-212 | `get_audit_logs` |

同时，对于 `stash_workorder`、`delete_stash` 中使用的 `current_user.user_id`、`confirm_workorder` 中使用的 `current_user.user_id`，保持不变（user_id 字段名未变）。

- [ ] **Step 3: 更新 CurrentUser 字段引用**

将路由文件中所有 `current_user.name` 替换为 `current_user.display_name`（约 4 处，分别在 confirm_workorder、review_workorder 调用中）。

将路由文件中所有 `current_user.department` 替换为 `current_user.department_code`（约 4 处，同上）。

- [ ] **Step 4: 更新 admin 端点 — 添加 require_admin**

将 `list_sync_failures`（第 248-252 行）和 `retry_sync`（第 274-279 行）的 `current_user: CurrentUser = Depends(get_current_user)` 替换为 `current_user: CurrentUser = Depends(require_admin)`。

- [ ] **Step 5: 验证模块可导入**

```bash
cd backend && python -c "from app.routers.review import router, admin_router; print('router OK')"
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/review.py
git commit -m "feat: add role-based access control to API endpoints"
```

---

### Task 7: 后端 — 更新 CORS origins 和环境变量

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/.env`（如存在）

**Interfaces:**
- None (infrastructure change)

- [ ] **Step 1: 更新 CORS origins**

在 `backend/app/main.py` 第 76 行，将：

```python
allow_origins=["http://localhost:5193"],
```

替换为：

```python
allow_origins=[
    "http://localhost:5193",
    "https://shouhou-gongdan-dev.example.com",
],
```

- [ ] **Step 2: 更新 .env 文件（如存在）**

检查 `backend/.env` 文件内容。如果包含 `JWT_SECRET` 行，删除它。确保包含 Keycloak 配置：

```env
KEYCLOAK_ISSUER=http://10.8.6.32:18080/realms/company-dev
KEYCLOAK_JWKS_URL=http://10.8.6.32:18080/realms/company-dev/protocol/openid-connect/certs
KEYCLOAK_AUDIENCE=shouhou-gongdan-api
```

- [ ] **Step 3: 验证应用启动**

```bash
cd backend && timeout 5 python -c "
from app.main import app
print('App created successfully')
print('Routes:', [r.path for r in app.routes])
" 2>&1 || true
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/main.py backend/.env
git commit -m "chore: update CORS origins for dev environment and Keycloak env vars"
```

---

### Task 8: 后端 — 重写测试

**Files:**
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_auth.py`
- Modify: `backend/tests/test_review_api.py`（字段引用更新）
- Create: `backend/tests/test_keycloak_auth.py`

**Interfaces:**
- Produces: `mock_jwks_client` fixture, `rs256_key_pair` fixture, `make_test_token` helper

- [ ] **Step 1: 生成测试用 RS256 密钥对**

```bash
cd backend && python -c "
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# 生成 2048-bit RSA 密钥对
key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)

private_pem = key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

public_pem = key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

print('=== PRIVATE KEY ===')
print(private_pem.decode())
print('=== PUBLIC KEY ===')
print(public_pem.decode())
"
```

- [ ] **Step 2: 更新 `backend/tests/conftest.py`**

```python
import json
import pytest
from unittest.mock import patch, MagicMock
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import jwt as pyjwt

from app.auth.schemas import CurrentUser


@pytest.fixture(scope="session")
def rsa_key_pair():
    """生成 RS256 测试密钥对（session 级别，所有测试共享）。"""
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return {
        "private_key": private_pem.decode(),
        "public_key": public_pem.decode(),
        "private_key_obj": key,
    }


@pytest.fixture
def make_test_token(rsa_key_pair):
    """工厂 fixture：创建测试 JWT token。"""
    def _make(
        sub="test-user-001",
        preferred_username="testuser",
        name="测试用户",
        email="test@example.com",
        department_code="IT",
        department_name="信息技术部",
        roles=None,
        issuer="http://10.8.6.32:18080/realms/company-dev",
        audience="shouhou-gongdan-api",
        expired=False,
    ):
        if roles is None:
            roles = ["agent_user"]
        import time
        payload = {
            "sub": sub,
            "preferred_username": preferred_username,
            "name": name,
            "email": email,
            "department_code": department_code,
            "department_name": department_name,
            "resource_access": {
                "shouhou-gongdan-api": {
                    "roles": roles,
                },
            },
            "iss": issuer,
            "aud": [audience, "account"],
            "iat": int(time.time()),
            "exp": int(time.time()) + 300 if not expired else int(time.time()) - 60,
        }
        token = pyjwt.encode(
            payload,
            rsa_key_pair["private_key_obj"],
            algorithm="RS256",
        )
        return token
    return _make


@pytest.fixture
def current_user():
    """当前用户 fixture — 默认 agent_user 角色。"""
    return CurrentUser(
        user_id="test-user-001",
        username="testuser",
        display_name="测试用户",
        email="test@example.com",
        department_code="IT",
        department_name="信息技术部",
        roles=["agent_user"],
    )


@pytest.fixture
def admin_user():
    """管理员 fixture — agent_admin 角色。"""
    return CurrentUser(
        user_id="admin-001",
        username="admin",
        display_name="管理员",
        email="admin@example.com",
        department_code="IT",
        department_name="信息技术部",
        roles=["agent_admin"],
    )
```

- [ ] **Step 3: 重写 `backend/tests/test_auth.py`**

```python
import pytest
from unittest.mock import patch, MagicMock
import jwt as pyjwt

from app.auth.dependencies import get_current_user, require_admin, require_any_role
from app.auth.schemas import CurrentUser


class TestGetCurrentUser:
    """测试 get_current_user 依赖 — 从 Bearer token 解析用户。"""

    @pytest.mark.asyncio
    async def test_parses_valid_token(self, make_test_token):
        """有效 token 应正确解析为 CurrentUser。"""
        token = make_test_token(
            sub="user-001",
            preferred_username="zhangsan",
            name="张三",
            email="zhangsan@example.com",
            department_code="CS",
            department_name="客服部",
            roles=["agent_user"],
        )
        from fastapi.security import HTTPAuthorizationCredentials
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=token
        )

        with patch("app.auth.dependencies.decode_jwt") as mock_decode:
            import json
            # 模拟 decode_jwt 返回 claims（绕过真实 JWKS 验证）
            mock_decode.return_value = pyjwt.decode(
                token,
                options={"verify_signature": False},
                algorithms=["RS256"],
            )

            from app.auth.dependencies import get_current_user
            user = await get_current_user(credentials)

            assert user.user_id == "user-001"
            assert user.username == "zhangsan"
            assert user.display_name == "张三"
            assert user.email == "zhangsan@example.com"
            assert user.department_code == "CS"
            assert user.department_name == "客服部"
            assert "agent_user" in user.roles

    @pytest.mark.asyncio
    async def test_handles_missing_optional_claims(self, make_test_token):
        """可选 claim 缺失时返回空字符串。"""
        token = make_test_token(
            sub="user-002",
            preferred_username="",
            name="",
            email="",
            department_code="",
            department_name="",
            roles=[],
        )
        from fastapi.security import HTTPAuthorizationCredentials
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=token
        )

        with patch("app.auth.dependencies.decode_jwt") as mock_decode:
            mock_decode.return_value = pyjwt.decode(
                token,
                options={"verify_signature": False},
                algorithms=["RS256"],
            )
            user = await get_current_user(credentials)

            assert user.user_id == "user-002"
            assert user.username == ""
            assert user.roles == []

    @pytest.mark.asyncio
    async def test_extracts_multiple_roles(self, make_test_token):
        """多角色用户应解析出所有角色。"""
        token = make_test_token(roles=["agent_admin", "agent_manager"])
        from fastapi.security import HTTPAuthorizationCredentials
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=token
        )

        with patch("app.auth.dependencies.decode_jwt") as mock_decode:
            mock_decode.return_value = pyjwt.decode(
                token,
                options={"verify_signature": False},
                algorithms=["RS256"],
            )
            user = await get_current_user(credentials)

            assert "agent_admin" in user.roles
            assert "agent_manager" in user.roles
            assert len(user.roles) == 2


class TestRequireAdmin:
    """测试 require_admin 角色检查。"""

    @pytest.mark.asyncio
    async def test_allows_admin_role(self, admin_user):
        """agent_admin 角色应通过检查。"""
        result = await require_admin(admin_user)
        assert result.user_id == admin_user.user_id

    @pytest.mark.asyncio
    async def test_rejects_non_admin_role(self, current_user):
        """非 admin 角色应返回 403。"""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            await require_admin(current_user)
        assert exc.value.status_code == 403
        assert "管理员" in exc.value.detail


class TestRequireAnyRole:
    """测试 require_any_role 角色检查。"""

    @pytest.mark.asyncio
    async def test_allows_valid_roles(self, current_user):
        """agent_user 角色应通过检查。"""
        result = await require_any_role(current_user)
        assert result.user_id == current_user.user_id

    @pytest.mark.asyncio
    async def test_rejects_no_roles(self, make_test_token):
        """无有效角色的用户应返回 403。"""
        user = CurrentUser(
            user_id="no-role-001",
            username="norole",
            display_name="No Role",
            email="",
            department_code="",
            department_name="",
            roles=[],
        )
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            await require_any_role(user)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_rejects_unknown_roles(self):
        """不在三个角色范围内的角色应返回 403。"""
        user = CurrentUser(
            user_id="unknown-001",
            username="unknown",
            display_name="Unknown",
            email="",
            department_code="",
            department_name="",
            roles=["some_other_role"],
        )
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            await require_any_role(user)
        assert exc.value.status_code == 403
```

- [ ] **Step 4: 创建 `backend/tests/test_keycloak_auth.py` — JWT 解码测试**

```python
import pytest
from unittest.mock import patch, MagicMock
import jwt as pyjwt

from app.auth.jwt import decode_jwt


class TestDecodeJwt:
    """测试 decode_jwt — RS256 JWT 校验。"""

    @pytest.mark.asyncio
    async def test_decodes_valid_rs256_token(self, make_test_token, rsa_key_pair):
        """有效的 RS256 token 应正确解码。"""
        token = make_test_token()

        # Mock JWKS client 返回测试公钥
        mock_signing_key = MagicMock()
        mock_signing_key.key = rsa_key_pair["public_key"]

        mock_client = MagicMock()
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

        with patch("app.auth.jwt._get_jwks_client", return_value=mock_client):
            payload = await decode_jwt(token)

            assert payload["sub"] == "test-user-001"
            assert payload["preferred_username"] == "testuser"

    @pytest.mark.asyncio
    async def test_rejects_expired_token(self, make_test_token, rsa_key_pair):
        """过期 token 应返回 401。"""
        token = make_test_token(expired=True)

        mock_signing_key = MagicMock()
        mock_signing_key.key = rsa_key_pair["public_key"]

        mock_client = MagicMock()
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

        from fastapi import HTTPException
        with patch("app.auth.jwt._get_jwks_client", return_value=mock_client):
            with pytest.raises(HTTPException) as exc:
                await decode_jwt(token)
            assert exc.value.status_code == 401
            assert "过期" in exc.value.detail

    @pytest.mark.asyncio
    async def test_rejects_wrong_issuer(self, make_test_token, rsa_key_pair):
        """issuer 不匹配的 token 应返回 401。"""
        token = make_test_token(issuer="http://wrong-issuer/realms/evil")

        mock_signing_key = MagicMock()
        mock_signing_key.key = rsa_key_pair["public_key"]

        mock_client = MagicMock()
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

        from fastapi import HTTPException
        with patch("app.auth.jwt._get_jwks_client", return_value=mock_client):
            with pytest.raises(HTTPException) as exc:
                await decode_jwt(token)
            assert exc.value.status_code == 401
            assert "签发" in exc.value.detail

    @pytest.mark.asyncio
    async def test_rejects_wrong_audience(self, make_test_token, rsa_key_pair):
        """audience 不匹配的 token 应返回 401。"""
        token = make_test_token(audience="wrong-audience")

        mock_signing_key = MagicMock()
        mock_signing_key.key = rsa_key_pair["public_key"]

        mock_client = MagicMock()
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

        from fastapi import HTTPException
        with patch("app.auth.jwt._get_jwks_client", return_value=mock_client):
            with pytest.raises(HTTPException) as exc:
                await decode_jwt(token)
            assert exc.value.status_code == 401
            assert "受众" in exc.value.detail
```

- [ ] **Step 5: 更新其他测试文件中的 CurrentUser 构造**

检查 `backend/tests/test_review_api.py`、`backend/tests/test_lock_api.py`、`backend/tests/test_review_integration.py`、`backend/tests/test_services.py` 等文件中是否有旧版 `CurrentUser(user_id=..., name=..., role=..., department=...)` 构造，更新为新字段。

搜索命令：
```bash
cd backend && grep -rn "CurrentUser\|current_user\." tests/ | grep -v __pycache__
```

如果找到旧字段引用，逐一替换：
- `name=` → `display_name=`
- `role=` → `roles=[...,]`
- `department=` → `department_code=`
- `current_user.name` → `current_user.display_name`
- `current_user.department` → `current_user.department_code`

- [ ] **Step 6: 运行所有测试**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: 所有测试通过（或合理跳过）。

- [ ] **Step 7: Commit**

```bash
git add backend/tests/
git commit -m "test: rewrite auth tests for Keycloak RS256 JWT and RBAC"
```

---

### Task 9: 前端 — 安装 keycloak-js

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: 安装 keycloak-js**

```bash
cd frontend && npm install keycloak-js@^26.0.0
```

- [ ] **Step 2: 验证安装**

```bash
cd frontend && node -e "const KC = require('keycloak-js'); console.log('keycloak-js version:', 'OK')" 2>/dev/null || \
node -e "import('keycloak-js').then(m => console.log('keycloak-js OK'))"
```

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: install keycloak-js for OIDC authentication"
```

---

### Task 10: 前端 — 创建 Auth 模块 (keycloak 实例 + useAuth Hook + Provider)

**Files:**
- Create: `frontend/src/auth/keycloak.ts`
- Create: `frontend/src/auth/useAuth.ts`
- Create: `frontend/src/auth/KeycloakProvider.tsx`
- Create: `frontend/src/auth/index.ts`

- [ ] **Step 1: 创建 `frontend/src/auth/keycloak.ts`**

```typescript
import Keycloak from 'keycloak-js';

const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL || 'http://10.8.6.32:18080',
  realm: import.meta.env.VITE_KEYCLOAK_REALM || 'company-dev',
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || 'shouhou-gongdan-web',
});

export default keycloak;
```

- [ ] **Step 2: 创建 `frontend/src/auth/useAuth.ts`**

```typescript
import { useContext } from 'react';
import { AuthContext, type AuthContextValue } from './KeycloakProvider';

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within a KeycloakProvider');
  }
  return context;
}

export type { AuthUser } from './KeycloakProvider';
```

- [ ] **Step 3: 创建 `frontend/src/auth/KeycloakProvider.tsx`**

```typescript
import {
  createContext,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import keycloak from './keycloak';

export interface AuthUser {
  sub: string;
  preferred_username: string;
  name: string;
  email: string;
  department_code: string;
  department_name: string;
  roles: string[];
}

export interface AuthContextValue {
  authenticated: boolean;
  user: AuthUser | null;
  token: string | null;
  login: () => void;
  logout: () => void;
  hasRole: (role: string) => boolean;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

function parseUser(token: string): AuthUser {
  // 安全地从 access_token 解析 claims（不校验签名，仅用于前端展示）
  const payload = JSON.parse(atob(token.split('.')[1]));
  const roles: string[] =
    payload.resource_access?.['shouhou-gongdan-api']?.roles ?? [];
  return {
    sub: payload.sub ?? '',
    preferred_username: payload.preferred_username ?? '',
    name: payload.name ?? '',
    email: payload.email ?? '',
    department_code: payload.department_code ?? '',
    department_name: payload.department_name ?? '',
    roles,
  };
}

interface Props {
  children: ReactNode;
}

export function KeycloakProvider({ children }: Props) {
  const [authenticated, setAuthenticated] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const initialized = useRef(false);
  const refreshTimer = useRef<ReturnType<typeof setInterval>>();

  // 定时刷新 token（过期前 30 秒）
  const startTokenRefresh = useCallback(() => {
    if (refreshTimer.current) {
      clearInterval(refreshTimer.current);
    }
    refreshTimer.current = setInterval(() => {
      keycloak
        .updateToken(30)
        .then((refreshed) => {
          if (refreshed && keycloak.token) {
            setToken(keycloak.token);
            setUser(parseUser(keycloak.token));
          }
        })
        .catch(() => {
          // 刷新失败，跳转登录
          setAuthenticated(false);
          setUser(null);
          setToken(null);
        });
    }, 30_000); // 每 30 秒检查一次
  }, []);

  // 初始化 Keycloak
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    keycloak
      .init({
        onLoad: 'check-sso',
        pkceMethod: 'S256',
        silentCheckSsoRedirectUri:
          window.location.origin + '/silent-check-sso.html',
      })
      .then((auth) => {
        if (auth && keycloak.token) {
          setAuthenticated(true);
          setToken(keycloak.token);
          setUser(parseUser(keycloak.token));
          startTokenRefresh();
        }
      })
      .catch((err) => {
        console.error('Keycloak init failed:', err);
      });
  }, [startTokenRefresh]);

  const login = useCallback(() => {
    keycloak.login({
      redirectUri: window.location.origin + '/callback',
    });
  }, []);

  const logout = useCallback(() => {
    if (refreshTimer.current) {
      clearInterval(refreshTimer.current);
    }
    keycloak.logout({
      redirectUri: window.location.origin + '/',
    });
  }, []);

  const hasRole = useCallback(
    (role: string): boolean => {
      return user?.roles.includes(role) ?? false;
    },
    [user],
  );

  const value: AuthContextValue = {
    authenticated,
    user,
    token,
    login,
    logout,
    hasRole,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
```

- [ ] **Step 4: 创建 `frontend/src/auth/index.ts`**

```typescript
export { KeycloakProvider } from './KeycloakProvider';
export { useAuth } from './useAuth';
export type { AuthUser, AuthContextValue } from './KeycloakProvider';
export { default as keycloak } from './keycloak';
```

- [ ] **Step 5: 验证 TypeScript 编译**

```bash
cd frontend && npx tsc --noEmit src/auth/*.ts src/auth/*.tsx 2>&1 | head -20
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/auth/
git commit -m "feat: add Keycloak auth module (Provider + useAuth hook)"
```

---

### Task 11: 前端 — 更新 API 层，使用 Keycloak token

**Files:**
- Modify: `frontend/src/api/review.ts`

- [ ] **Step 1: 修改 `frontend/src/api/review.ts`**

将第 23-40 行替换为：

```typescript
import keycloak from '../auth/keycloak';

function getToken(): string {
  return keycloak.token ?? '';
}

function authHeaders(): HeadersInit {
  const token = getToken();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}
```

同时删除第 20-22 行关于 `VITE_API_TOKEN` 的注释：

```typescript
// 删除这三行注释：
// 认证 token 通过环境变量 VITE_API_TOKEN 注入。
// 本地开发：在 .env.local 中设置 VITE_API_TOKEN=your-dev-jwt
// 生产环境：构建时由 CI/CD 注入或通过 OAuth2 登录流程获取后写入
```

替换为：

```typescript
// 认证 token 由 Keycloak 实例自动管理（含自动刷新）。
```

另外，在 `authHeaders()` 之前添加 401 响应处理逻辑。将现有的 `authHeaders()` 调用改为通过统一的 fetch wrapper：

```typescript
async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  let res = await fetch(url, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers as Record<string, string> || {}) },
  });

  if (res.status === 401) {
    // 尝试刷新 token
    try {
      await keycloak.updateToken(30);
      res = await fetch(url, {
        ...options,
        headers: { ...authHeaders(), ...(options.headers as Record<string, string> || {}) },
      });
    } catch {
      // 刷新失败，跳转登录
      keycloak.login({ redirectUri: window.location.origin + '/callback' });
      throw new Error('认证已过期，正在跳转登录...');
    }
  }

  return res;
}
```

然后将所有 `fetch(BASE + '...', { headers: authHeaders(), ... })` 调用替换为 `authFetch(BASE + '...', { ... })`。

- [ ] **Step 2: TypeScript 编译检查**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/review.ts
git commit -m "feat: replace VITE_API_TOKEN with Keycloak-managed token in API layer"
```

---

### Task 12: 前端 — 更新 App.tsx 和环境变量

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/.env`

- [ ] **Step 1: 修改 `frontend/src/App.tsx`**

```typescript
import { KeycloakProvider } from './auth';
import { useAuth } from './auth';
import { ReviewWorkbench } from './workbench/ReviewWorkbench';

function AppContent() {
  const { authenticated, login } = useAuth();

  if (!authenticated) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">售后工单审核工作台</h1>
          <p className="text-gray-500 mb-6">请登录后使用</p>
          <button
            onClick={login}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            统一身份认证登录
          </button>
        </div>
      </div>
    );
  }

  return <ReviewWorkbench />;
}

function App() {
  return (
    <KeycloakProvider>
      <AppContent />
    </KeycloakProvider>
  );
}

export default App;
```

- [ ] **Step 2: 创建 `frontend/.env`**

```env
VITE_KEYCLOAK_URL=http://10.8.6.32:18080
VITE_KEYCLOAK_REALM=company-dev
VITE_KEYCLOAK_CLIENT_ID=shouhou-gongdan-web
```

- [ ] **Step 3: TypeScript 编译检查**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/.env
git commit -m "feat: add login gate with Keycloak OIDC to App entry"
```

---

### Task 13: 端到端验证

- [ ] **Step 1: 确保后端环境变量已配置**

```bash
cd backend && cat .env | grep -E "KEYCLOAK_|DATABASE_URL|REDIS_URL"
```

确认 KEYCLOAK_ISSUER、KEYCLOAK_JWKS_URL、KEYCLOAK_AUDIENCE 均已设置。

- [ ] **Step 2: 启动后端**

```bash
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8093 &
```

验证健康检查：
```bash
curl http://localhost:8093/health
```

Expected: `{"status":"ok","service":"shouhou-gongdan-backend"}`

- [ ] **Step 3: 验证 API 401 保护**

```bash
curl -s http://localhost:8093/api/workorders | head -5
```

Expected: 返回 403（无 Authorization header），不再是 500。

- [ ] **Step 4: 启动前端**

```bash
cd frontend && npm run dev &
```

访问 `http://localhost:5193`，验证：
- 未登录时显示登录按钮
- 点击登录按钮跳转到 Keycloak 登录页
- 登录后回到应用，显示 ReviewWorkbench

- [ ] **Step 5: Commit 最终状态**

```bash
git add -A
git commit -m "chore: finalize Keycloak integration with E2E verification"
```
