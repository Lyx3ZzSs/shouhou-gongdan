import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from fastapi import HTTPException

from app.auth.jwt import decode_jwt


@pytest.fixture(autouse=True)
def patch_settings():
    """自动为所有测试注入 Keycloak 配置 mock。"""
    with patch("app.auth.jwt.settings") as mock_settings:
        mock_settings.KEYCLOAK_JWKS_URL = "http://10.8.6.32:18080/realms/company-dev/protocol/openid-connect/certs"
        mock_settings.KEYCLOAK_ISSUER = "http://10.8.6.32:18080/realms/company-dev"
        mock_settings.KEYCLOAK_AUDIENCE = "shouhou-gongdan-api"
        yield mock_settings


class TestDecodeJwt:
    """测试 decode_jwt — RS256 JWT 校验。"""

    @pytest.mark.asyncio
    async def test_decodes_valid_rs256_token(self, make_test_token, rsa_key_pair):
        """有效的 RS256 token 应正确解码。"""
        token = make_test_token()

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

        with patch("app.auth.jwt._get_jwks_client", return_value=mock_client):
            with pytest.raises(HTTPException) as exc:
                await decode_jwt(token)
            assert exc.value.status_code == 401
            assert "受众" in exc.value.detail
