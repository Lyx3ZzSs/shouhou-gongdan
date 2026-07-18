import pytest
from unittest.mock import AsyncMock, MagicMock, call
from app.services.audit_service import AuditService
from app.services.bad_case_service import BadCaseService
from app.schemas.review import FieldChange


@pytest.mark.asyncio
async def test_audit_service_batch_create():
    db = AsyncMock()
    service = AuditService(db)
    changes = [
        FieldChange(op="replace", path="/problem_category_l1", field_label="问题分类",
                    old_value="数据问题", new_value="工程问题"),
        FieldChange(op="replace", path="/order_level", field_label="受理单级别",
                    old_value="P3", new_value="P2"),
    ]
    await service.batch_create(
        workorder_id="WO001",
        session_id="sess-001",
        changes=changes,
        operator_id="agent-001",
        operator_name="张三",
    )
    assert db.add_all.call_count == 1
    # 验证传入了 2 条审计日志
    args = db.add_all.call_args[0][0]
    assert len(args) == 2
    assert args[0].field_path == "/problem_category_l1"
    assert args[1].field_path == "/order_level"


@pytest.mark.asyncio
async def test_bad_case_service_batch_create():
    db = AsyncMock()
    service = BadCaseService(db)
    changes = [
        FieldChange(op="replace", path="/problem_category_l1", field_label="问题分类",
                    old_value="数据问题", new_value="工程问题"),
    ]
    await service.batch_create(
        workorder_id="WO001",
        audit_log_ids=[1],
        changes=changes,
    )
    assert db.add_all.call_count == 1
    args = db.add_all.call_args[0][0]
    assert len(args) == 1
    assert args[0].ai_value == "数据问题"
    assert args[0].human_value == "工程问题"
