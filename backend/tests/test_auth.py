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

        with patch("app.auth.dependencies.settings.AUTH_ENABLED", True), \
             patch("app.auth.dependencies.decode_jwt") as mock_decode:
            mock_decode.return_value = pyjwt.decode(
                token,
                options={"verify_signature": False},
                algorithms=["RS256"],
            )

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

        with patch("app.auth.dependencies.settings.AUTH_ENABLED", True), \
             patch("app.auth.dependencies.decode_jwt") as mock_decode:
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

        with patch("app.auth.dependencies.settings.AUTH_ENABLED", True), \
             patch("app.auth.dependencies.decode_jwt") as mock_decode:
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
    async def test_rejects_no_roles(self):
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
