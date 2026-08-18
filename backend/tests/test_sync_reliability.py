import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.clients.xiaoshouyi import (
    CreateWorkOrderRequest,
    XIAOSHOUYI_REQUEST_FIELDS,
    XiaoShouYiClient,
    XiaoShouYiUncertainError,
    map_db_to_xiaoshouyi,
)
from app.services.review_service import background_sync_to_xiaoshouyi, recover_orphan_syncs


class _SessionContext:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, *_args):
        return False


def _session_factory(*dbs):
    queue = list(dbs)
    return lambda: _SessionContext(queue.pop(0))


def _result(*, rowcount=1, mapping=None, rows=None):
    value = MagicMock(rowcount=rowcount)
    value.mappings.return_value.first.return_value = mapping
    value.mappings.return_value.all.return_value = rows or []
    return value


@pytest.mark.asyncio
async def test_recovered_sync_uses_existing_claim_and_does_not_claim_again():
    read_db = AsyncMock()
    read_db.execute = AsyncMock(return_value=_result(mapping={
        "ticket_id": 1, "field_overrides": {},
    }))
    write_db = AsyncMock()
    client = SimpleNamespace(create_work_order=AsyncMock(return_value=SimpleNamespace(external_id="XSY-1")))

    with patch("app.services.review_service._get_ticket_dict", AsyncMock(return_value={})), \
         patch("app.services.review_service.get_xiaoshouyi_client", return_value=client):
        status = await background_sync_to_xiaoshouyi(
            "WO-1", "key-1", _session_factory(read_db, write_db), already_claimed=True,
        )

    assert status == "synced"
    assert read_db.execute.await_count == 1  # 只读详情，没有重复执行认领 UPDATE
    client.create_work_order.assert_awaited_once()


@pytest.mark.asyncio
async def test_post_that_never_returns_converges_to_uncertain(monkeypatch):
    claim_db = AsyncMock()
    claim_db.execute = AsyncMock(return_value=_result(rowcount=1))
    read_db = AsyncMock()
    read_db.execute = AsyncMock(return_value=_result(mapping={
        "ticket_id": 1, "field_overrides": {},
    }))
    uncertain_db = AsyncMock()

    async def hangs(_request):
        await asyncio.Event().wait()

    monkeypatch.setattr("app.services.review_service.settings.XIAOSHOUYI_SYNC_TIMEOUT_SECONDS", 0.01)
    client = SimpleNamespace(create_work_order=AsyncMock(side_effect=hangs))
    with patch("app.services.review_service._get_ticket_dict", AsyncMock(return_value={})), \
         patch("app.services.review_service.get_xiaoshouyi_client", return_value=client):
        status = await background_sync_to_xiaoshouyi(
            "WO-1", "key-1", _session_factory(claim_db, read_db, uncertain_db),
        )

    assert status == "uncertain"
    values = uncertain_db.execute.await_args.args[0].compile().params
    assert values["sync_status"] == "uncertain"


@pytest.mark.asyncio
async def test_response_disconnect_is_uncertain_and_not_retried():
    client = XiaoShouYiClient()
    client._base_url = "https://example.test"
    client._get_token = AsyncMock(return_value="token")
    http = AsyncMock()
    http.post = AsyncMock(side_effect=httpx.RemoteProtocolError("response ended"))
    client._get_client = AsyncMock(return_value=http)

    with pytest.raises(XiaoShouYiUncertainError):
        await client.create_work_order(CreateWorkOrderRequest())
    assert http.post.await_count == 1


@pytest.mark.asyncio
async def test_recovery_claim_handoff_marks_task_as_already_claimed():
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[
        _result(rowcount=0),
        _result(rows=[{"id": "WO-1", "sync_idempotency_key": "key-1"}]),
        _result(rows=[]),
    ])
    scheduled = MagicMock()

    count = await recover_orphan_syncs(_session_factory(db, db), scheduled)

    assert count == 1
    assert scheduled.call_args.args[-1] is True


@pytest.mark.asyncio
async def test_stale_syncing_converges_to_uncertain_without_resend():
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_result(rowcount=1), _result(rows=[])])
    scheduled = MagicMock()

    count = await recover_orphan_syncs(_session_factory(db, db), scheduled)

    assert count == 0
    scheduled.assert_not_called()


def test_http_client_uses_native_timeout_and_ignores_system_proxy(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7890")
    client = XiaoShouYiClient()

    async def inspect():
        http = await client._get_client()
        try:
            assert http.trust_env is False
            assert http.timeout.connect == 5.0
            assert http.timeout.read == client._settings.XIAOSHOUYI_SYNC_TIMEOUT_SECONDS
        finally:
            await http.aclose()

    asyncio.run(inspect())


def test_salesforce_body_contains_only_documented_fields():
    request = map_db_to_xiaoshouyi({
        "entityType": "1101004550001",
        "name": "测试工单",
        "relatedAttachment__c": "故障照片.pdf",
        "idempotencyKey__c": "must-not-leak",
    })

    body = request.to_api_body()
    assert set(body) == set(XIAOSHOUYI_REQUEST_FIELDS)
    assert body["entityType"] == "11010045500001"
    assert "relatedAttachment__c" not in body
    assert "idempotencyKey__c" not in body
