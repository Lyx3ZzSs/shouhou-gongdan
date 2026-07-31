import logging

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.auth.jwt import decode_jwt
from app.auth.schemas import CurrentUser
from app.core.config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

VALID_ROLES = {"agent_admin", "agent_manager", "agent_user"}

# AUTH_ENABLED=false 时使用的默认开发用户（拥有全部角色）
_DEV_USER = CurrentUser(
    user_id="dev-user",
    username="dev",
    display_name="开发用户",
    email="dev@localhost",
    department_code="DEV",
    department_name="开发部",
    roles=["agent_admin", "agent_manager", "agent_user"],
)


def _extract_roles(payload: dict) -> list[str]:
    """从 resource_access.shouhou-gongdan-api.roles 提取角色列表。"""
    try:
        return payload.get("resource_access", {}).get("shouhou-gongdan-api", {}).get("roles", [])
    except (AttributeError, KeyError):
        return []


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentUser:
    """从 Bearer token 解析当前用户。AUTH_ENABLED=false 时返回开发用户。"""
    if not settings.AUTH_ENABLED:
        return _DEV_USER

    if credentials is None:
        raise HTTPException(status_code=401, detail="未提供认证令牌")

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
