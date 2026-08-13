import pytest
from unittest.mock import AsyncMock, MagicMock, call
from app.services.audit_service import AuditService
from app.services.bad_case_service import BadCaseService
from app.schemas.review import FieldChange


@pytest.mark.asyncio
async def test_audit_service_batch_create():
    db = MagicMock()
    db.flush = AsyncMock()
    service = AuditService(db)
    changes = [
        FieldChange(op="replace", path="/problemType1__c", field_label="问题分类-1级",
                    old_value="现场问题-1", new_value="数据优化-2"),
        FieldChange(op="replace", path="/problemLevel__c", field_label="问题等级",
                    old_value="1", new_value="2"),
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
    assert args[0].field_path == "/problemType1__c"
    assert args[1].field_path == "/problemLevel__c"


@pytest.mark.asyncio
async def test_bad_case_service_batch_create():
    db = MagicMock()
    db.flush = AsyncMock()
    service = BadCaseService(db)
    changes = [
        FieldChange(op="replace", path="/problemType1__c", field_label="问题分类-1级",
                    old_value="现场问题-1", new_value="数据优化-2"),
    ]
    await service.batch_create(
        workorder_id="WO001",
        audit_log_ids=[1],
        changes=changes,
    )
    assert db.add_all.call_count == 1
    args = db.add_all.call_args[0][0]
    assert len(args) == 1
    assert args[0].ai_value == "现场问题-1"
    assert args[0].human_value == "数据优化-2"
