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
    token: str = None,
    db: AsyncSession = None,
) -> CurrentUser:
    if token and token.startswith("Bearer "):
        token = token[7:]
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
