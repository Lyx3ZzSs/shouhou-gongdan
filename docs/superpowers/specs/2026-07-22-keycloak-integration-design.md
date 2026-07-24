# Keycloak 统一认证接入 — 设计文档

> 日期：2026-07-22
> 系统：售后工单审核工作台 (shouhou-gongdan)

## 一、背景与目标

将 shouhou-gongdan 接入公司统一认证平台 Keycloak (`http://10.8.6.32:18080`)，替换当前的占位 JWT 认证（HS256 + 静态密钥），实现标准的 OIDC 认证与 RBAC 授权。

## 二、决策记录

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 集成策略 | 直接替换 | 最小影响，无历史包袱 |
| 角色权限 | admin 仅 agent_admin，业务三角色均可 | 按接入文档建议 |
| 前端 OIDC 库 | keycloak-js | 公司统一 Keycloak，集成简单 |
| React 集成 | 自封装 Provider + Hook | 逻辑不复杂，透明可控 |
| 配置方式 | 全部环境变量 | 不硬编码，适配多环境 |

## 三、架构总览

```
┌─────────────────────────────────────────────────┐
│                   Keycloak                       │
│          http://10.8.6.32:18080                  │
│              realm: company-dev                  │
│  ┌─────────────────┐ ┌───────────────────────┐   │
│  │ shouhou-gongdan-│ │ shouhou-gongdan-api   │   │
│  │ web (public)    │ │ (confidential, RS256) │   │
│  └────────┬────────┘ └───────────┬───────────┘   │
└───────────┼──────────────────────┼───────────────┘
            │ Auth Code + PKCE     │ JWT Validation
            ▼                      ▼
   ┌────────────────┐    ┌────────────────────┐
   │  Frontend       │    │  Backend           │
   │  React 18       │───▶│  FastAPI           │
   │  port 5193      │    │  port 8093         │
   │  keycloak-js    │    │  JWKS RS256        │
   │  KeycloakProvider│   │  RBAC (3 roles)    │
   └────────────────┘    └────────────────────┘
```

## 四、后端设计

### 4.1 Config 变更 (`app/core/config.py`)

**新增：**
```python
KEYCLOAK_ISSUER: str = ""       # 从 .env 注入
KEYCLOAK_JWKS_URL: str = ""     # 从 .env 注入
KEYCLOAK_AUDIENCE: str = ""     # 从 .env 注入
```

**移除：** `JWT_SECRET` 字段及校验逻辑。

### 4.2 Auth 模块重写 (`app/auth/`)

新文件结构：
```
app/auth/
├── __init__.py
├── dependencies.py   # get_current_user, require_admin, require_any_role
├── jwt.py            # decode_jwt, JWKS 缓存, RS256 签名校验
└── schemas.py        # CurrentUser dataclass
```

**CurrentUser 新字段：**
```python
@dataclass
class CurrentUser:
    user_id: str          # sub — Keycloak 用户唯一 ID
    username: str         # preferred_username
    display_name: str     # name
    email: str            # email
    department_code: str  # department_code
    department_name: str  # department_name
    roles: list[str]      # resource_access.shouhou-gongdan-api.roles
```

**JWT 校验流程 (`jwt.py`)：**
1. 从 JWKS 端点获取公钥（内存缓存 1 小时，失败自动重试）
2. 使用 `python-jose` 或 `pyjwt` 验证 RS256 签名
3. 验证 `iss` = `KEYCLOAK_ISSUER`
4. 验证 `exp` 未过期
5. 验证 `aud` 包含 `KEYCLOAK_AUDIENCE`
6. 提取 claims → 构造 CurrentUser

**角色检查依赖 (`dependencies.py`)：**
```python
async def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if "agent_admin" not in user.roles:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user

async def require_any_role(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    valid = {"agent_admin", "agent_manager", "agent_user"}
    if not (valid & set(user.roles)):
        raise HTTPException(status_code=403, detail="无有效角色")
    return user
```

**移除：** 旧的 `validate_token`、`decode_jwt`（HS256 版本）、`CurrentUser`（旧字段）。

### 4.3 Router 权限变更 (`app/routers/review.py`)

| 端点 | 旧依赖 | 新依赖 |
|------|--------|--------|
| `GET /api/workorders` | `get_current_user` | `get_current_user` + `require_any_role` |
| `GET /api/workorders/{id}` | `get_current_user` | `get_current_user` + `require_any_role` |
| `POST /api/workorders/{id}/confirm` | `get_current_user` | `get_current_user` + `require_any_role` |
| `POST /api/workorders/{id}/stash` | `get_current_user` | `get_current_user` + `require_any_role` |
| `GET /api/workorders/{id}/stash` | `get_current_user` | `get_current_user` + `require_any_role` |
| `DELETE /api/workorders/{id}/stash` | `get_current_user` | `get_current_user` + `require_any_role` |
| `GET /api/workorders/{id}/audit-logs` | `get_current_user` | `get_current_user` + `require_any_role` |
| `GET /api/admin/sync-failures` | `get_current_user` | `get_current_user` + `require_admin` |
| `POST /api/admin/sync-failures/{id}/retry` | `get_current_user` | `get_current_user` + `require_admin` |
| `GET /health` | 无 | 无（保持公开） |

### 4.4 CORS 更新 (`app/main.py`)

```python
allow_origins=[
    "http://localhost:5193",
    "https://shouhou-gongdan-dev.example.com",
]
```

### 4.5 服务层适配

`review_service.py` 中引用 `current_user.department` 的地方改为 `current_user.department_code`，`current_user.role` 改为 `current_user.roles`。

## 五、前端设计

### 5.1 新增依赖

```json
"keycloak-js": "^26.0.0"
```

### 5.2 文件结构

```
frontend/src/auth/
├── keycloak.ts           # Keycloak 实例 + 初始化配置
├── KeycloakProvider.tsx  # React Context Provider
└── useAuth.ts            # useAuth Hook（含 User 类型）
```

### 5.3 keycloak.ts

```typescript
import Keycloak from 'keycloak-js';

const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL,
  realm: import.meta.env.VITE_KEYCLOAK_REALM,
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID,
});

export default keycloak;
```

### 5.4 KeycloakProvider

职责：
- `onInit`: 调用 `keycloak.init({ onLoad: 'check-sso', pkceMethod: 'S256' })`
- 未认证: 调用 `keycloak.login({ redirectUri })` 跳转登录
- 已认证: 解析 token claims，构造 user 对象，存入 context
- 定时刷新: token 过期前 30 秒调用 `keycloak.updateToken(30)`
- `onLogout`: 调用 `keycloak.logout({ redirectUri })`
- 暴露 `authenticated`, `user`, `token` 状态

### 5.5 useAuth Hook

```typescript
interface AuthUser {
  sub: string;
  preferred_username: string;
  name: string;
  email: string;
  department_code: string;
  department_name: string;
  roles: string[];
}

function useAuth(): {
  authenticated: boolean;
  user: AuthUser | null;
  token: string | null;
  login: () => void;
  logout: () => void;
  hasRole: (role: string) => boolean;
}
```

### 5.6 API 层变更 (`api/review.ts`)

- 删除 `getToken()` 中对 `VITE_API_TOKEN` 的读取
- `authHeaders()` 改为从全局 Keycloak 实例获取 token
- 401 响应时: 尝试 `keycloak.updateToken()` 刷新，失败则跳转登录

### 5.7 App.tsx 变更

```tsx
import { KeycloakProvider } from './auth/KeycloakProvider';

function App() {
  return (
    <KeycloakProvider>
      <ReviewWorkbench />
    </KeycloakProvider>
  );
}
```

### 5.8 Vite 环境变量

```env
VITE_KEYCLOAK_URL=http://10.8.6.32:18080
VITE_KEYCLOAK_REALM=company-dev
VITE_KEYCLOAK_CLIENT_ID=shouhou-gongdan-web
# 删除 VITE_API_TOKEN
```

## 六、测试影响

| 文件 | 影响 | 处理 |
|------|------|------|
| `tests/test_auth.py` | JWT 校验逻辑完全变化 | 重写，本地生成 RS256 测试 token + mock JWKS |
| `tests/conftest.py` | 需 mock JWKS 端点 | 新增 `mock_jwks` fixture，返回本地公钥 |
| `tests/test_review_api.py` | 依赖注入链不变 | 更新 fixture 中 CurrentUser 字段 |
| 其他 service 测试 | `current_user.department` → `department_code` | 更新字段引用 |

## 七、环境变量汇总

### 后端 `.env`
```env
# 新增（替代 JWT_SECRET）
KEYCLOAK_ISSUER=http://10.8.6.32:18080/realms/company-dev
KEYCLOAK_JWKS_URL=http://10.8.6.32:18080/realms/company-dev/protocol/openid-connect/certs
KEYCLOAK_AUDIENCE=shouhou-gongdan-api
```

### 前端 `.env`
```env
# 新增（替代 VITE_API_TOKEN）
VITE_KEYCLOAK_URL=http://10.8.6.32:18080
VITE_KEYCLOAK_REALM=company-dev
VITE_KEYCLOAK_CLIENT_ID=shouhou-gongdan-web
```

## 八、不涉及范围

- 不引入前端路由库（当前单页面）
- 不做细粒度工单数据过滤（agent_user 暂与 agent_admin 看到相同数据）
- docker-compose 不变，不添加本地 Keycloak 容器
