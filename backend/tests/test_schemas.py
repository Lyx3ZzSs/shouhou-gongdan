import pytest
from app.schemas.review import FieldChange, ReviewRequest, ALLOWED_FIELDS

def test_field_change_valid():
    fc = FieldChange(
        op="replace",
        path="/problem_category_l1",
        field_label="问题分类",
        old_value="数据问题",
        new_value="工程问题",
    )
    assert fc.op == "replace"
    assert fc.old_value == "数据问题"

def test_review_request_confirm():
    req = ReviewRequest(
        session_id="sess-001",
        version=1,
        changes=[
            FieldChange(
                op="replace", path="/problem_category_l1",
                field_label="问题分类", old_value="数据问题",
                new_value="工程问题",
            )
        ],
        reject_reason=None,
    )
    assert req.reject_reason is None
    assert len(req.changes) == 1

def test_review_request_reject():
    req = ReviewRequest(
        session_id="sess-002",
        version=1,
        changes=[],
        reject_reason="分类与客户描述不符",
    )
    assert req.reject_reason == "分类与客户描述不符"

def test_allowed_fields_contains_required():
    assert "station_name" in ALLOWED_FIELDS
    assert "problem_category_l1" in ALLOWED_FIELDS
    assert "responsible_person" in ALLOWED_FIELDS
    assert "order_level" in ALLOWED_FIELDS
    assert "customer_level" in ALLOWED_FIELDS
    assert "product_type" in ALLOWED_FIELDS

def test_field_change_rejects_invalid_op():
    with pytest.raises(ValueError):
        FieldChange(
            op="invalid",
            path="/x",
            field_label="X",
            old_value=None,
            new_value=None,
        )
