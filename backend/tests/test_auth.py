import pytest
from unittest.mock import patch
from app.auth.dependencies import validate_token, CurrentUser


@pytest.mark.asyncio
async def test_get_current_user_from_valid_token():
    """operator_id 从 JWT token payload 提取，非客户端传入"""
    token = "eyJ.valid.token"
    with patch("app.auth.dependencies.decode_jwt") as mock_decode:
        mock_decode.return_value = {
            "sub": "agent-001",
            "name": "张三",
            "role": "customer_service_agent",
            "department": "售后部",
        }
        user = validate_token(token)
        assert user.user_id == "agent-001"
        assert user.name == "张三"
        assert user.role == "customer_service_agent"
        assert user.department == "售后部"


@pytest.mark.asyncio
async def test_get_current_user_rejects_non_agent_role():
    token = "eyJ.valid.token"
    with patch("app.auth.dependencies.decode_jwt") as mock_decode:
        mock_decode.return_value = {
            "sub": "user-001",
            "name": "李四",
            "role": "viewer",
            "department": "售后部",
        }
        with pytest.raises(Exception) as exc:
            validate_token(token)
        assert "403" in str(exc.value) or "Forbidden" in str(exc.value)


@pytest.mark.asyncio
async def test_get_current_user_rejects_invalid_jwt():
    token = "invalid.token"
    with patch("app.auth.dependencies.decode_jwt") as mock_decode:
        import jwt
        mock_decode.side_effect = jwt.PyJWTError("Invalid token")
        with pytest.raises(jwt.PyJWTError):
            validate_token(token)
