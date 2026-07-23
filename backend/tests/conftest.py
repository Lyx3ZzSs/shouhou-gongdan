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
        import time
        if roles is None:
            roles = ["agent_user"]
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
