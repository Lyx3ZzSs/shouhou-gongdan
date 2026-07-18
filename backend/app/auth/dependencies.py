from dataclasses import dataclass
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()


@dataclass
class CurrentUser:
    user_id: str
    name: str
    role: str
    department: str


def validate_token(token: str) -> CurrentUser:
    """Validate a raw JWT token string and return a CurrentUser."""
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


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    token = credentials.credentials
    return validate_token(token)


def decode_jwt(token: str) -> dict:
    # TODO: 替换为实际的 JWT 解码逻辑（项目级配置）
    import jwt
    from app.core.config import settings
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"无效的认证令牌: {e}")
