"""当前审核模型的 PostgreSQL 集成测试。

覆盖 ticket/ticket_view + workorder_review + review_submission 的确认、驳回和幂等回放。
测试使用独立数据库 shouhou_gongdan_test，不接触开发业务数据。
"""

from pathlib import Path
import os
from unittest.mock import AsyncMock

import asyncpg
import pytest
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.schemas.review import ConfirmRequest, FieldChange
from app.services.review_service import ReviewService
from app.services.import_service import import_workorders

TEST_DB_NAME = "shouhou_gongdan_test"
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", settings.DATABASE_URL)


def _url(database: str) -> str:
    return make_url(TEST_DATABASE_URL).set(database=database).render_as_string(
        hide_password=False,
    )


async def _connect(database: str):
    url = make_url(TEST_DATABASE_URL)
    return await asyncpg.connect(
        host=url.host or "localhost",
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        database=database,
        timeout=5,
    )


@pytest.fixture
async def engine():
    try:
        admin = await _connect("postgres")
    except Exception as exc:
        pytest.skip(f"PostgreSQL is not available — skipping integration tests: {exc}")
    try:
        try:
            await admin.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
        except asyncpg.DuplicateDatabaseError:
            pass
    finally:
        await admin.close()

    conn = await _connect(TEST_DB_NAME)
    try:
        await conn.execute(Path("../schema_init.sql").read_text(encoding="utf-8"))
    finally:
        await conn.close()

    value = create_async_engine(_url(TEST_DB_NAME), echo=False)
    yield value
    await value.dispose()
    admin = await _connect("postgres")
    try:
        await admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname=$1 AND pid <> pg_backend_pid()", TEST_DB_NAME,
        )
        await admin.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"')
    finally:
        await admin.close()


@pytest.fixture
async def db(engine):
    async with engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE review_submission, bad_case_sample, workorder_audit_log, "
            "workorder_stash, workorder_review, ticket_attachment, ticket, "
            "wechat_session, user_ledger, wechat_user RESTART IDENTITY CASCADE"
        ))
        await conn.execute(text(
            "INSERT INTO wechat_user (user_id, nick_name) VALUES ('wx-e2e', '测试客户')"
        ))
        await conn.execute(text("""
            INSERT INTO wechat_session (
                id, customer_id, start_time, customer_msgs, service_msgs, source, status
            ) VALUES (
                8001, 'wx-e2e', '2026-08-12 09:30:00+08', '[]', '[]', '微信', 'processed'
            )
        """))
        await conn.execute(text("""
            INSERT INTO user_ledger (
                user_id, station_name, name, phone, province, case_account_id,
                project_name, customer_short_name, service_cycle_start,
                service_cycle_end, is_overdue_service
            ) VALUES (
                'wx-e2e', '测试风场', '测试客户', '13800000000', '河北', 'ACC-001',
                '测试项目', '测试客户简称', '2026-01-01', '2026-12-31', 'false'
            )
        """))
        await conn.execute(text("""
            INSERT INTO ticket (
                id, session_id, "ownerId", "dimDepart", "entityType",
                name, "case_Source", "feedbackChannel_c", "workOrderStatus__c",
                "caseDescription", "caseStatus", "problemLevel_c", "problemType1__c",
                "problemType2__c", "problemType3__c", "problemResponsible_c",
                "problemDept_c", "needCallBack__c", "needOnSite__c"
            ) VALUES (
                9001, 8001, 'u1', 'd1', '11010045500001',
                '测试场站功率控制异常', '1',
                '1', '1', '测试场站功率控制持续异常，需要技术人员排查',
                '1', '1', '2', '17', '47', 'engineer-1', '技术支持部', '2', '2'
            )
        """))
        await conn.execute(text("""
            INSERT INTO workorder_review (
                id, ticket_id, version, lock_fencing_token, review_status
            ) VALUES ('WO-E2E-001', 9001, 1, 7, 'pending_review')
        """))
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


def _request(*, session_id="sess-1", key="idem-1", reject_reason=None, changes=None):
    return ConfirmRequest(
        session_id=session_id, version=1, idempotency_key=key,
        lock_fencing_token=7, reject_reason=reject_reason,
        changes=changes or [],
    )


def _service(db):
    service = ReviewService(db)
    service.lock_service = AsyncMock()
    service.lock_service.get_owner.return_value = {
        "operator_id": "agent-1", "operator_name": "审核员",
        "locked_at": "2026-08-13T00:00:00+00:00", "fencing_token": 7,
    }
    return service


@pytest.mark.asyncio
async def test_confirm_persists_override_audit_bad_case_and_submission(db):
    change = FieldChange(
        op="replace", path="/problemType2__c", field_label="问题分类-2级",
        old_value="17", new_value="15",
    )
    result = await _service(db).confirm(
        workorder_id="WO-E2E-001", request=_request(changes=[change]),
        operator_id="agent-1", operator_name="审核员",
        operator_department="技术支持部", should_sync=False,
    )
    assert result.response["status"] == "confirmed"
    row = (await db.execute(text(
        "SELECT review_status, version, field_overrides->>'problemType2__c' "
        "FROM workorder_review WHERE id='WO-E2E-001'"
    ))).one()
    assert tuple(row) == ("confirmed", 2, "15")
    assert (await db.execute(text("SELECT count(*) FROM workorder_audit_log"))).scalar() == 1
    assert (await db.execute(text("SELECT count(*) FROM bad_case_sample"))).scalar() == 1
    assert (await db.execute(text("SELECT count(*) FROM review_submission"))).scalar() == 1


@pytest.mark.asyncio
async def test_reject_persists_reason_without_bad_case(db):
    result = await _service(db).confirm(
        workorder_id="WO-E2E-001",
        request=_request(reject_reason="分类信息不足，请重新补充"),
        operator_id="agent-1", operator_name="审核员",
        operator_department="技术支持部", should_sync=False,
    )
    assert result.response["status"] == "rejected"
    row = (await db.execute(text(
        "SELECT review_status, reject_count, last_reject_reason "
        "FROM workorder_review WHERE id='WO-E2E-001'"
    ))).one()
    assert tuple(row) == ("returned", 1, "分类信息不足，请重新补充")
    assert (await db.execute(text("SELECT count(*) FROM bad_case_sample"))).scalar() == 0


@pytest.mark.asyncio
async def test_idempotent_retry_replays_response_after_lock_release(db):
    request = _request()
    service = _service(db)
    first = await service.confirm(
        workorder_id="WO-E2E-001", request=request,
        operator_id="agent-1", operator_name="审核员",
        operator_department="技术支持部", should_sync=False,
    )
    await db.rollback()
    service.lock_service.get_owner.return_value = None
    retry = await service.confirm(
        workorder_id="WO-E2E-001", request=request.model_copy(update={"lock_fencing_token": 99}),
        operator_id="agent-1", operator_name="审核员",
        operator_department="技术支持部", should_sync=False,
    )
    assert retry.response == first.response
    assert (await db.execute(text("SELECT count(*) FROM review_submission"))).scalar() == 1


@pytest.mark.asyncio
async def test_current_source_view_preserves_domain_contract(db):
    row = (await db.execute(text("""
        SELECT "caseSource", "feedbackChannel__c", "problemLevel__c",
               "caseAccountId", "stationName", "projectName__c",
               "isOverdueService__c", source_created_at
        FROM ticket_view WHERE id=9001
    """))).one()
    assert tuple(row[:7]) == ('1', '1', '1', 'ACC-001', '测试风场', '测试项目', '2')
    assert row.source_created_at is not None


@pytest.mark.asyncio
async def test_import_current_wechat_ticket_is_idempotent(db):
    await db.execute(text("DELETE FROM workorder_review"))
    await db.commit()
    assert await import_workorders(db) == 1
    assert await import_workorders(db) == 0
    row = (await db.execute(text("""
        SELECT ticket_id, initiator, initiator_department
        FROM workorder_review
    """))).one()
    assert tuple(row) == (9001, '测试客户', '微信')
