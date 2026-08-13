import pytest
from app.schemas.review import FieldChange, ReviewRequest, ALLOWED_FIELDS

def test_field_change_valid():
    fc = FieldChange(
        op="replace",
        path="/problemType1__c",
        field_label="问题分类-1级",
        old_value="现场问题-1",
        new_value="数据优化-2",
    )
    assert fc.op == "replace"
    assert fc.old_value == "现场问题-1"

def test_review_request_confirm():
    req = ReviewRequest(
        session_id="sess-001",
        version=1,
        changes=[
            FieldChange(
                op="replace", path="/problemType1__c",
                field_label="问题分类-1级", old_value="现场问题-1",
                new_value="数据优化-2",
            )
        ],
        reject_reason=None,
        lock_fencing_token=1,
    )
    assert req.reject_reason is None
    assert len(req.changes) == 1

def test_review_request_reject():
    req = ReviewRequest(
        session_id="sess-002",
        version=1,
        changes=[],
        reject_reason="分类与客户描述不符",
        lock_fencing_token=1,
    )
    assert req.reject_reason == "分类与客户描述不符"

def test_allowed_fields_contains_required():
    assert "ownerId" in ALLOWED_FIELDS
    assert "name" in ALLOWED_FIELDS
    assert "caseSource" in ALLOWED_FIELDS
    assert "caseStatus" in ALLOWED_FIELDS
    assert "problemType1__c" in ALLOWED_FIELDS
    assert "problemResponsible__c" in ALLOWED_FIELDS
    assert "custLevel1__c" in ALLOWED_FIELDS
    assert "workOrderStatus__c" in ALLOWED_FIELDS
    assert "defectFlag__c" not in ALLOWED_FIELDS

def test_field_change_rejects_invalid_op():
    with pytest.raises(ValueError):
        FieldChange(
            op="invalid",
            path="/x",
            field_label="X",
            old_value=None,
            new_value=None,
        )


def test_remove_rejects_non_empty_new_value():
    with pytest.raises(ValueError):
        FieldChange(op="remove", path="/remark__c", field_label="备注", new_value="绕过值")
