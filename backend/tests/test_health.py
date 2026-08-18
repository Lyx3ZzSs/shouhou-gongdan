from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_is_liveness_only():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_ready_returns_503_when_dependency_fails():
    session = AsyncMock()
    session.__aenter__.return_value.execute.side_effect = RuntimeError("db down")
    lock = AsyncMock()
    lock.redis.ping.return_value = True
    with patch("app.main.async_session", return_value=session), \
         patch("app.main.get_lock_service", return_value=lock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"] == {"database": False, "schema": False, "redis": True}


@pytest.mark.asyncio
async def test_ready_returns_503_when_ticket_id_schema_is_not_ready():
    session = AsyncMock()
    session.__aenter__.return_value.scalar.return_value = False
    lock = AsyncMock()
    lock.redis.ping.return_value = True
    with patch("app.main.async_session", return_value=session), \
         patch("app.main.get_lock_service", return_value=lock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"] == {"database": True, "schema": False, "redis": True}
