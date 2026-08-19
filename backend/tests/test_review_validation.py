from app.core.field_config import load_field_config
from app.services.review_validation import validate_workorder


def valid_workorder(**overrides):
    data = {
        "ownerId": "u1", "dimDepart": "d1", "name": "华北场站功率预测异常",
        "caseStatus": "1", "caseSource": "1", "feedbackChannel__c": "1",
        "workOrderStatus__c": "1", "caseDescription": "场站功率预测连续偏差，需排查气象数据。",
        "caseAccountId": "SPCZ202408210132", "projectName__c": "华北场站项目",
        "problemResponsible__c": "engineer-1", "problemDept__c": "技术支持部",
        "problemLevel__c": "1", "problemType1__c": "2", "problemType2__c": "17",
        "problemType3__c": "47", "needCallBack__c": "2", "needOnSite__c": "2",
    }
    data.update(overrides)
    return data


def test_valid_workorder_passes():
    result = validate_workorder(valid_workorder())
    assert result.valid
    assert result.blocking_count == 0


def test_required_and_invalid_enum_block():
    result = validate_workorder(valid_workorder(ownerId="", caseStatus="999"))
    assert not result.valid
    assert {i.code for i in result.issues} >= {"REQUIRED_FIELD_MISSING", "INVALID_ENUM_VALUE"}


def test_urgent_workorder_requires_owner_department_and_deadline():
    result = validate_workorder(valid_workorder(
        problemLevel__c="2", problemResponsible__c="", problemDept__c="", requireSolveTime__c="",
    ))
    assert result.blocking_count == 3
    assert all(i.code == "URGENT_FIELD_MISSING" for i in result.issues)


def test_onsite_callback_and_service_period_rules():
    result = validate_workorder(valid_workorder(
        needOnSite__c="1", caseAccountId="", projectName__c="",
        needCallBack__c="1", feedbackUserContact__c="",
        serviceCycleStart__c="2026-08-12", serviceCycleEnd__c="2026-08-11",
    ))
    assert {i.code for i in result.issues} >= {
        "ONSITE_CONTEXT_MISSING", "CALLBACK_CONTACT_MISSING", "SERVICE_PERIOD_INVALID",
    }


def test_high_risk_keyword_warns_without_blocking():
    result = validate_workorder(valid_workorder(caseDescription="场站发生AGC拉停，需要立即排查。"))
    assert result.valid
    assert any(i.code == "HIGH_RISK_KEYWORD" for i in result.issues)


def test_mixed_timezone_dates_are_compared_safely():
    result = validate_workorder(valid_workorder(
        serviceCycleStart__c="2026-08-12T08:00:00Z",
        serviceCycleEnd__c="2026-08-12 09:00:00",
    ))
    assert result.valid


def test_invalid_datetime_blocks():
    result = validate_workorder(valid_workorder(requireSolveTime__c="not-a-date"))
    assert not result.valid
    assert any(i.code == "INVALID_DATETIME" for i in result.issues)


def test_optional_contact_must_be_11_digits_when_present():
    assert validate_workorder(valid_workorder(feedbackUserContact__c="")).valid
    result = validate_workorder(valid_workorder(feedbackUserContact__c="123"))
    assert any(i.code == "INVALID_CONTACT_PHONE" for i in result.issues)


def test_high_risk_category_warns_without_keyword():
    result = validate_workorder(valid_workorder(
        problemType2__c="7", caseDescription="控制策略执行异常，请技术人员核对。",
    ))
    assert result.valid
    assert any(i.code == "HIGH_RISK_KEYWORD" for i in result.issues)


def test_special_order_requires_owner_department_and_deadline():
    result = validate_workorder(valid_workorder(
        workOrderStatus__c="5", problemResponsible__c="", problemDept__c="",
        requireSolveTime__c="",
    ))
    assert result.blocking_count == 3
    assert all(i.code == "SPECIAL_ORDER_FIELD_MISSING" for i in result.issues)


def test_category_parent_mapping_blocks_invalid_combination():
    config = load_field_config()
    original = config.review_rules["category_parents"]
    config.review_rules["category_parents"] = {
        "problemType2__c": {"17": ["1"]}, "problemType3__c": {},
    }
    try:
        result = validate_workorder(valid_workorder(
            problemType1__c="2", problemType2__c="17",
        ))
    finally:
        config.review_rules["category_parents"] = original
    assert any(i.code == "CATEGORY_COMBINATION_INVALID" for i in result.issues)
