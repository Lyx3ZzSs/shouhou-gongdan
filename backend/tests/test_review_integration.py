"""End-to-end integration tests for the review confirm/reject/idempotency flow.

Exercises the full stack: FastAPI router -> ReviewService -> database,
using a real PostgreSQL database (test database created/destroyed per session).

Pre-requisites:
    PostgreSQL must be running (docker compose up -d postgres).
    The test database 'shouhou_gongdan_test' is created automatically.

Key design decisions:
  - WorkOrder ORM model omits ~132 pre-existing columns, so the workorder
    table is created via raw SQL to include only the columns needed by tests.
  - LockService is patched to a no-op to avoid a Redis dependency.
  - Each test truncates all tables for a clean state.
  - Test database persists across test functions for speed; cleanup is
    done at module teardown.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy import make_url
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.exc import OperationalError

from app.main import app
from app.auth.dependencies import get_current_user, CurrentUser
from app.core.database import get_db
from app.core.config import settings

TEST_DB_NAME = "shouhou_gongdan_test"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_test_db_url() -> str:
    """Build the PostgreSQL connection URL for the test database."""
    url = make_url(settings.DATABASE_URL)
    return str(url.set(database=TEST_DB_NAME))


def _build_admin_db_url() -> str:
    """Build the PostgreSQL connection URL for the 'postgres' admin database."""
    url = make_url(settings.DATABASE_URL)
    return str(url.set(database="postgres"))


async def _ensure_test_db() -> None:
    """Create the test database if it does not already exist."""
    import asyncpg
    admin_url = _build_admin_db_url()
    try:
        conn = await asyncpg.connect(dsn=admin_url, timeout=5)
        try:
            await conn.execute(
                f'CREATE DATABASE "{TEST_DB_NAME}"'
            )
        except asyncpg.DuplicateDatabaseError:
            pass  # already exists
        finally:
            await conn.close()
    except Exception:
        # Connection failed — PostgreSQL is likely not running
        pytest.skip("PostgreSQL is not available — skipping integration tests")


async def _drop_test_db() -> None:
    """Drop the test database."""
    import asyncpg
    admin_url = _build_admin_db_url()
    try:
        conn = await asyncpg.connect(dsn=admin_url, timeout=5)
        try:
            await conn.execute(
                f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"'
            )
        finally:
            await conn.close()
    except Exception:
        pass  # best-effort cleanup


async def _create_workorder(engine, **fields) -> None:
    """Insert a workorder row via raw SQL."""
    defaults = dict(
        id="WO-E2E-DEFAULT",
        version=1,
        status="pending_review",
        station_name="测试场站",
        project_province="广东",
        problem_description="测试问题描述",
        problem_category_l1="数据问题",
        order_level="P3",
        responsible_person="李燕昆",
        responsible_department="数据中心",
        primary_department="数据中心",
        after_sales_person="李燕昆",
    )
    defaults.update(fields)
    cols = ", ".join(defaults.keys())
    placeholders = ", ".join(f":{k}" for k in defaults)
    async with AsyncSession(engine) as session:
        async with session.begin():
            await session.execute(
                text(f"INSERT INTO workorder ({cols}) VALUES ({placeholders})"),
                defaults,
            )


async def _fetch_one(engine, sql: str, **params):
    """Execute a raw SQL query and return the first row, or None."""
    async with AsyncSession(engine) as session:
        result = await session.execute(text(sql), params)
        return result.fetchone()


async def _count(engine, table: str, **where) -> int:
    """Count rows in *table* matching optional WHERE conditions."""
    if where:
        clause = " AND ".join(f"{k} = :{k}" for k in where)
        sql = f"SELECT COUNT(*) FROM {table} WHERE {clause}"
    else:
        sql = f"SELECT COUNT(*) FROM {table}"
    async with AsyncSession(engine) as session:
        result = await session.execute(text(sql), where or None)
        return result.scalar()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def _test_db_session():
    """Session-scoped: create test database once, drop at end.

    This is NOT a pytest fixture returned to tests — it's a setup/teardown
    hook that runs at session scope.  Tests use the function-scoped
    ``engine`` fixture below.
    """
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(_ensure_test_db())
    yield
    loop.run_until_complete(_drop_test_db())


@pytest.fixture(scope="function")
async def engine(_test_db_session):
    """Create a real PostgreSQL engine and ensure all tables exist.

    Truncates all tables at the start of each test for a clean state.
    """
    test_url = _build_test_db_url()
    _engine = create_async_engine(test_url, echo=False)

    # Ensure tables exist (idempotent — uses IF NOT EXISTS)
    async with _engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS workorder (
                id VARCHAR(64) PRIMARY KEY,
                version INTEGER DEFAULT 1 NOT NULL,
                status VARCHAR(32) DEFAULT 'pending_review',
                reviewed_at TIMESTAMP,
                reviewed_by VARCHAR(64),
                reject_count INTEGER DEFAULT 0 NOT NULL,
                last_reject_reason TEXT,
                last_rejected_by VARCHAR(64),
                last_rejected_at TIMESTAMP,
                sync_status VARCHAR(16) DEFAULT 'pending',
                station_name VARCHAR(255),
                project_province VARCHAR(255),
                problem_description TEXT,
                problem_category_l1 VARCHAR(255),
                order_level VARCHAR(32),
                responsible_person VARCHAR(255),
                responsible_department VARCHAR(255),
                primary_department VARCHAR(255),
                after_sales_person VARCHAR(255)
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS workorder_audit_log (
                id BIGSERIAL PRIMARY KEY,
                workorder_id VARCHAR(64) NOT NULL,
                session_id VARCHAR(64) NOT NULL,
                field_path VARCHAR(128) NOT NULL,
                field_label VARCHAR(64) NOT NULL,
                old_value TEXT,
                new_value TEXT,
                change_type VARCHAR(16) NOT NULL DEFAULT 'replace',
                operator_id VARCHAR(64) NOT NULL,
                operator_name VARCHAR(64),
                operated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_workorder
            ON workorder_audit_log(workorder_id)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_session
            ON workorder_audit_log(session_id)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_operator
            ON workorder_audit_log(operator_id)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_operated_at
            ON workorder_audit_log(operated_at)
        """))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bad_case_sample (
                id BIGSERIAL PRIMARY KEY,
                workorder_id VARCHAR(64) NOT NULL,
                audit_log_id BIGINT NOT NULL
                    REFERENCES workorder_audit_log(id),
                field_path VARCHAR(128) NOT NULL,
                ai_value TEXT,
                human_value TEXT,
                sample_status VARCHAR(16) NOT NULL DEFAULT 'pending',
                source VARCHAR(32) NOT NULL DEFAULT 'review_correction',
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_status
            ON bad_case_sample(sample_status)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_workorder
            ON bad_case_sample(workorder_id)
        """))

    # Truncate all tables for a clean test state
    async with _engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE TABLE bad_case_sample, workorder_audit_log, workorder CASCADE"
        ))

    yield _engine

    await _engine.dispose()


@pytest.fixture
def mock_user():
    return CurrentUser(
        user_id="agent-001",
        name="张三",
        role="customer_service_agent",
        department="售后部",
    )


@pytest.fixture
async def client(mock_user, engine):
    """FastAPI test client with auth + DB + LockService overrides."""
    app.dependency_overrides[get_current_user] = lambda: mock_user

    async def override_get_db():
        async with AsyncSession(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # Mock lock service to avoid a running Redis instance
    mock_lock = MagicMock()
    mock_lock.get_owner = AsyncMock(return_value={
        "operator_id": mock_user.user_id,
        "operator_name": mock_user.name,
        "locked_at": "2026-07-18T10:00:00+00:00",
    })
    with patch("app.routers.review.get_lock_service", return_value=mock_lock), \
         patch("app.services.lock_service.LockService.release"):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestReviewConfirmFlow:
    """Confirm flow: status change, audit logs, bad_case records."""

    async def test_full_confirm_flow(self, client, engine):
        """End-to-end confirm: workorder status updated, audit logs + bad_case
        records are written, version is incremented, reviewed_by is set."""
        # Arrange – create a workorder with pending_review status
        await _create_workorder(engine, id="WO-E2E-001")

        # Act – submit a confirm review with two changes
        resp = await client.post("/api/workorders/WO-E2E-001/review", json={
            "session_id": "e2e-sess-001",
            "version": 1,
            "changes": [
                {
                    "op": "replace",
                    "path": "/problem_category_l1",
                    "field_label": "问题分类",
                    "old_value": "数据问题",
                    "new_value": "工程问题",
                },
                {
                    "op": "replace",
                    "path": "/order_level",
                    "field_label": "受理单级别",
                    "old_value": "P3",
                    "new_value": "P2",
                },
            ],
            "reject_reason": None,
        })

        # Assert – HTTP response shape
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "confirmed"
        assert data["change_count"] == 2
        assert data["bad_case_count"] == 2
        assert data["next_status"] == "dispatching"
        assert data["review_id"] != "dup"
        assert data["review_id"].startswith("rev-")

        # Assert – workorder row updated
        row = await _fetch_one(
            engine,
            "SELECT status, version, reviewed_at, reviewed_by "
            "FROM workorder WHERE id = :id",
            id="WO-E2E-001",
        )
        assert row is not None
        assert row[0] == "confirmed"          # status
        assert row[1] == 2                     # version incremented
        assert row[2] is not None              # reviewed_at set
        assert row[3] == "张三"                 # reviewed_by

        # Assert – two audit log entries
        n_audit = await _count(
            engine, "workorder_audit_log",
            workorder_id="WO-E2E-001",
        )
        assert n_audit == 2

        # Assert – two bad_case_sample records
        n_bad = await _count(
            engine, "bad_case_sample",
            workorder_id="WO-E2E-001",
        )
        assert n_bad == 2


class TestReviewRejectFlow:
    """Reject flow: no bad_case, reject_count incremented."""

    async def test_full_reject_flow_no_bad_case(self, client, engine):
        """End-to-end reject: workorder reject_count incremented,
        last_reject_reason set, zero bad_case records created."""
        await _create_workorder(engine, id="WO-E2E-002",
                                project_province="北京",
                                problem_description="测试",
                                problem_category_l1="产品问题",
                                responsible_person="朱莉",
                                responsible_department="产品部",
                                primary_department="产品部",
                                after_sales_person="朱莉",
                                )

        resp = await client.post("/api/workorders/WO-E2E-002/review", json={
            "session_id": "e2e-sess-002",
            "version": 1,
            "changes": [],
            "reject_reason": "分类不准确需重新判定",
        })

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "rejected"
        assert data["bad_case_count"] == 0
        assert data["next_status"] == "pending_review"

        row = await _fetch_one(
            engine,
            "SELECT reject_count, last_reject_reason "
            "FROM workorder WHERE id = :id",
            id="WO-E2E-002",
        )
        assert row is not None
        assert row[0] == 1                           # reject_count
        assert row[1] == "分类不准确需重新判定"          # last_reject_reason

        n_bad = await _count(
            engine, "bad_case_sample",
            workorder_id="WO-E2E-002",
        )
        assert n_bad == 0


class TestReviewIdempotency:
    """Idempotency: duplicate session_id returns 'dup' result."""

    async def test_idempotency(self, client, engine):
        """Submitting the same session_id twice returns a 'dup' response
        and does NOT create duplicate audit-log or bad-case records."""
        await _create_workorder(engine, id="WO-E2E-001")
        resp1 = await client.post("/api/workorders/WO-E2E-001/review", json={
            "session_id": "e2e-sess-003",
            "version": 1,
            "changes": [
                {
                    "op": "replace",
                    "path": "/problem_category_l1",
                    "field_label": "问题分类",
                    "old_value": "数据问题",
                    "new_value": "工程问题",
                },
            ],
            "reject_reason": None,
        })
        assert resp1.status_code == 200, resp1.text
        row = await _fetch_one(
            engine,
            "SELECT version FROM workorder WHERE id = :id",
            id="WO-E2E-001",
        )
        current_version = row[0]
        assert current_version == 2

        # Act – same session_id again
        resp2 = await client.post("/api/workorders/WO-E2E-001/review", json={
            "session_id": "e2e-sess-003",
            "version": current_version,
            "changes": [],
            "reject_reason": None,
        })

        assert resp2.status_code == 200, resp2.text
        assert resp2.json()["review_id"] == "dup"

        n_audit = await _count(
            engine, "workorder_audit_log",
            workorder_id="WO-E2E-001",
        )
        assert n_audit == 1

        n_bad = await _count(
            engine, "bad_case_sample",
            workorder_id="WO-E2E-001",
        )
        assert n_bad == 1
