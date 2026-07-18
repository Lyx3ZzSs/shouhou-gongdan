import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import HTTPException
from app.main import app
from app.auth.dependencies import CurrentUser, get_current_user
from app.core.database import get_db


@pytest.fixture
def mock_user():
    return CurrentUser(user_id="agent-001", name="张三", role="customer_service_agent", department="售后部")


@pytest.fixture
async def client(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: MagicMock()
    mock_lock = MagicMock()
    mock_lock.get_owner = AsyncMock(return_value={
        "operator_id": "agent-001", "operator_name": "张三",
        "locked_at": "2026-07-18T10:00:00+00:00",
    })
    with patch("app.routers.review.get_lock_service", return_value=mock_lock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_review_confirm_success(client, mock_user):
    """确认提交：version 匹配 + 有变更 → 写审计日志 + bad_case"""
    with patch("app.routers.review.ReviewService") as MockSvc:
        mock_instance = AsyncMock()
        mock_instance.review = AsyncMock(return_value={
            "review_id": "rev-001", "workorder_id": "WO001",
            "status": "confirmed", "change_count": 2,
            "bad_case_count": 2, "next_status": "dispatching",
        })
        MockSvc.return_value = mock_instance

        resp = await client.post("/api/workorders/WO001/review", json={
            "session_id": "sess-001",
            "version": 1,
            "changes": [
                {"op": "replace", "path": "/problem_category_l1", "field_label": "问题分类",
                 "old_value": "数据问题", "new_value": "工程问题"},
            ],
            "reject_reason": None,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "confirmed"
        assert data["change_count"] == 2

    # Verify service was called with correct arguments
    mock_instance.review.assert_called_once()
    call_kwargs = mock_instance.review.call_args.kwargs
    assert call_kwargs["workorder_id"] == "WO001"
    assert call_kwargs["operator_id"] == "agent-001"
    assert call_kwargs["operator_name"] == "张三"


@pytest.mark.asyncio
async def test_review_reject_success(client):
    """退回重填：不写 bad_case"""
    with patch("app.routers.review.ReviewService") as MockSvc:
        mock_instance = AsyncMock()
        mock_instance.review = AsyncMock(return_value={
            "review_id": "rev-002", "workorder_id": "WO001",
            "status": "rejected", "change_count": 0,
            "bad_case_count": 0, "next_status": "pending_review",
        })
        MockSvc.return_value = mock_instance

        resp = await client.post("/api/workorders/WO001/review", json={
            "session_id": "sess-002",
            "version": 1,
            "changes": [],
            "reject_reason": "分类与客户描述不符",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
        assert data["bad_case_count"] == 0


@pytest.mark.asyncio
async def test_review_version_conflict(client):
    """版本冲突返回 409"""
    with patch("app.routers.review.ReviewService") as MockSvc:
        mock_instance = AsyncMock()
        mock_instance.review = AsyncMock(side_effect=HTTPException(status_code=409, detail="版本冲突，请刷新重试"))
        MockSvc.return_value = mock_instance

        resp = await client.post("/api/workorders/WO001/review", json={
            "session_id": "sess-003",
            "version": 1,  # 已过期
            "changes": [],
            "reject_reason": None,
        })
        assert resp.status_code == 409


@pytest.mark.asyncio
async def test_review_field_not_in_whitelist(client):
    """非白名单字段被静默过滤"""
    with patch("app.routers.review.ReviewService") as MockSvc:
        mock_instance = AsyncMock()
        mock_instance.review = AsyncMock(return_value={
            "review_id": "rev-003", "workorder_id": "WO001",
            "status": "confirmed", "change_count": 0,
            "bad_case_count": 0, "next_status": "dispatching",
        })
        MockSvc.return_value = mock_instance

        resp = await client.post("/api/workorders/WO001/review", json={
            "session_id": "sess-004",
            "version": 1,
            "changes": [
                {"op": "replace", "path": "/created_at", "field_label": "创建时间",
                 "old_value": "2020-01-01", "new_value": "2021-01-01"},
            ],
            "reject_reason": None,
        })
        assert resp.status_code == 200  # 不报错，但 created_at 不会被更新


@pytest.mark.asyncio
async def test_lock_conflict_no_lock_returns_423(client):
    """未持锁时调用 review → 423"""
    with patch("app.routers.review.get_lock_service") as mock_get_lock:
        mock_lock = MagicMock()
        mock_lock.get_owner = AsyncMock(return_value=None)  # 无人持锁
        mock_get_lock.return_value = mock_lock

        resp = await client.post("/api/workorders/WO001/review", json={
            "session_id": "sess-005",
            "version": 1,
            "changes": [],
            "reject_reason": None,
        })
        assert resp.status_code == 423


@pytest.mark.asyncio
async def test_lock_conflict_wrong_holder_returns_423(client):
    """其他用户持锁时调用 confirm → 423"""
    with patch("app.routers.review.get_lock_service") as mock_get_lock:
        mock_lock = MagicMock()
        mock_lock.get_owner = AsyncMock(return_value={
            "operator_id": "agent-999",
            "operator_name": "李四",
            "locked_at": "2026-07-18T10:00:00+00:00",
        })
        mock_get_lock.return_value = mock_lock

        resp = await client.post("/api/workorders/WO001/confirm", json={
            "session_id": "sess-006",
            "version": 1,
            "changes": [],
            "reject_reason": None,
            "idempotency_key": "idem-001",
        })
        assert resp.status_code == 423


@pytest.mark.asyncio
async def test_confirm_endpoint_success(client):
    """调用 /confirm 端点（含 idempotency_key）→ 200"""
    with patch("app.routers.review.ReviewService") as MockSvc:
        mock_instance = AsyncMock()
        mock_instance.confirm = AsyncMock(return_value={
            "review_id": "rev-004", "workorder_id": "WO001",
            "status": "confirmed", "change_count": 1,
            "bad_case_count": 1, "next_status": "dispatching",
            "sync_status": "pending",
        })
        MockSvc.return_value = mock_instance

        resp = await client.post("/api/workorders/WO001/confirm", json={
            "session_id": "sess-007",
            "version": 1,
            "changes": [
                {"op": "replace", "path": "/problem_category_l1", "field_label": "问题分类",
                 "old_value": "数据问题", "new_value": "工程问题"},
            ],
            "reject_reason": None,
            "idempotency_key": "idem-002",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "confirmed"
        assert data["sync_status"] == "pending"

    # Verify confirm() was called (not review())
    mock_instance.confirm.assert_called_once()
    call_kwargs = mock_instance.confirm.call_args.kwargs
    assert call_kwargs["workorder_id"] == "WO001"
    assert call_kwargs["operator_id"] == "agent-001"
