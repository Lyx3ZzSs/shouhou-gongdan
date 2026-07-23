import logging

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
