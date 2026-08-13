import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.auth.dependencies import get_current_user, CurrentUser
from app.core.database import get_db
from unittest.mock import AsyncMock, MagicMock

LOCK_TTL = 300


@pytest.fixture
def mock_current_user():
    return CurrentUser(
        user_id="agent-001",
        username="zhangsan",
        display_name="张三",
        email="zhangsan@test.com",
        department_code="SH",
        department_name="售后部",
        roles=["agent_user"],
    )


@pytest.fixture
async def client(mock_current_user):
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    db = AsyncMock()
    status_result = MagicMock()
    status_result.mappings.return_value.first.return_value = {
        "review_status": "pending_review", "lock_fencing_token": 0,
    }
    db.execute.return_value = status_result
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def redis():
    import redis.asyncio as aioredis

    r = aioredis.from_url("redis://localhost")
    try:
        await r.ping()
    except Exception:
        await r.aclose()
        pytest.skip("Redis is not available — skipping lock integration tests")
    yield r
    await r.flushdb()
    await r.aclose()


@pytest.mark.asyncio
async def test_acquire_lock_success(client, redis):
    """首次获取锁成功"""
    resp = await client.post("/api/workorders/WO001/lock")
    assert resp.status_code == 200
    data = resp.json()
    assert data["locked"] is True
    assert data["owner"] == "张三"
    assert data["fencing_token"] >= 1


@pytest.mark.asyncio
async def test_acquire_lock_returns_owner_when_locked_by_other(client, redis):
    """锁已被他人持有时返回持有者信息"""
    # 先由 agent-002 获取锁
    await redis.set(
        "review_lock:WO002", "agent-002:李四:2026-07-16T10:00:00", ex=LOCK_TTL
    )
    resp = await client.post("/api/workorders/WO002/lock")
    assert resp.status_code == 200
    data = resp.json()
    assert data["locked"] is False
    assert data["owner"] == "李四"


@pytest.mark.asyncio
async def test_release_lock_only_by_owner(client, redis):
    """非持有者释放锁返回 403"""
    await redis.set(
        "review_lock:WO003", "agent-002:李四:2026-07-16T10:00:00", ex=LOCK_TTL
    )
    resp = await client.delete("/api/workorders/WO003/lock", headers={"X-Lock-Fencing-Token": "1"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_heartbeat_only_by_owner(client, redis):
    """非持有者心跳续期返回 423"""
    await redis.set(
        "review_lock:WO004", "agent-002:李四:2026-07-16T10:00:00", ex=LOCK_TTL
    )
    resp = await client.put("/api/workorders/WO004/lock", headers={"X-Lock-Fencing-Token": "1"})
    assert resp.status_code == 423


@pytest.mark.asyncio
async def test_acquire_lock_idempotent_for_owner(client, redis):
    """G1: 同一持有者重复获取锁幂等成功"""
    # 首次获取
    resp1 = await client.post("/api/workorders/WO005/lock")
    assert resp1.status_code == 200
    assert resp1.json()["locked"] is True
    assert resp1.json()["owner"] == "张三"

    # 相同持有者再次获取
    resp2 = await client.post("/api/workorders/WO005/lock")
    assert resp2.status_code == 200
    assert resp2.json()["locked"] is True
    assert resp2.json()["owner"] == "张三"
    assert resp2.json()["fencing_token"] == resp1.json()["fencing_token"]


@pytest.mark.asyncio
async def test_new_owner_gets_higher_fencing_token(client, redis):
    first = await client.post("/api/workorders/WO009/lock")
    await client.delete("/api/workorders/WO009/lock", headers={"X-Lock-Fencing-Token": str(first.json()["fencing_token"])})
    second = await client.post("/api/workorders/WO009/lock")
    assert second.json()["fencing_token"] > first.json()["fencing_token"]


@pytest.mark.asyncio
async def test_heartbeat_expired_lock(client, redis):
    """G2: 已过期的锁心跳返回 423"""
    resp = await client.put("/api/workorders/WO006/lock", headers={"X-Lock-Fencing-Token": "1"})
    assert resp.status_code == 423
    assert "已过期" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_release_lock_by_owner_success(client, redis):
    """G3: 持有者释放锁成功"""
    # 先获取锁
    acquired = await client.post("/api/workorders/WO007/lock")
    resp = await client.delete("/api/workorders/WO007/lock", headers={"X-Lock-Fencing-Token": str(acquired.json()["fencing_token"])})
    assert resp.status_code == 200
    assert resp.json()["status"] == "released"


@pytest.mark.asyncio
async def test_heartbeat_by_owner_success(client, redis):
    """G4: 持有者心跳续期成功"""
    # 先获取锁
    acquired = await client.post("/api/workorders/WO008/lock")
    resp = await client.put("/api/workorders/WO008/lock", headers={"X-Lock-Fencing-Token": str(acquired.json()["fencing_token"])})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
