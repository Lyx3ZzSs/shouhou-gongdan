"""服务工单确认前校验。保持为纯函数，便于复用和表驱动测试。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.field_config import load_field_config


class ValidationIssue(BaseModel):
    code: str
    severity: Literal["blocking", "warning", "info"]
    field: str | None = None
    related_fields: list[str] = Field(default_factory=list)
    message: str


class ValidationResult(BaseModel):
    valid: bool
    blocking_count: int
    warning_count: int
    issues: list[ValidationIssue]


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _date(value: Any) -> datetime | None:
    if _blank(value):
        return None
    text = str(value).strip()
    if text.isdigit():
        try:
            return datetime.fromtimestamp(int(text), tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def validate_workorder(data: dict[str, Any]) -> ValidationResult:
    issues: list[ValidationIssue] = []
    config = load_field_config()
    rules = config.review_rules

    for field in config.fields:
        value = data.get(field.key)
        if field.required and _blank(value):
            issues.append(ValidationIssue(
                code="REQUIRED_FIELD_MISSING", severity="blocking",
                field=field.key, message=f"{field.name}未填写（必填字段）",
            ))
        if field.options and not _blank(value):
            allowed = {str(option["value"]) for option in field.options}
            if str(value) not in allowed:
                issues.append(ValidationIssue(
                    code="INVALID_ENUM_VALUE", severity="blocking",
                    field=field.key, message=f"{field.name}不是有效选项",
                ))

    contact = str(data.get("feedbackUserContact__c") or "").strip()
    if contact and (len(contact) != 11 or not contact.isdigit()):
        issues.append(ValidationIssue(
            code="INVALID_CONTACT_PHONE", severity="blocking",
            field="feedbackUserContact__c", message="反馈人联系方式须为 11 位手机号",
        ))

    if not _blank(data.get("problemType2__c")) and _blank(data.get("problemType1__c")):
        issues.append(ValidationIssue(
            code="CATEGORY_PARENT_MISSING", severity="blocking",
            field="problemType1__c", related_fields=["problemType2__c"],
            message="已选择二级问题分类，必须同时选择一级分类",
        ))
    if not _blank(data.get("problemType3__c")) and _blank(data.get("problemType2__c")):
        issues.append(ValidationIssue(
            code="CATEGORY_PARENT_MISSING", severity="blocking",
            field="problemType2__c", related_fields=["problemType3__c"],
            message="已选择三级问题分类，必须同时选择二级分类",
        ))

    for child_key, parent_key in (("problemType2__c", "problemType1__c"),
                                  ("problemType3__c", "problemType2__c")):
        child, parent = str(data.get(child_key) or ""), str(data.get(parent_key) or "")
        allowed_parents = rules.get("category_parents", {}).get(child_key, {}).get(child)
        if child and parent and allowed_parents and parent not in {str(v) for v in allowed_parents}:
            issues.append(ValidationIssue(
                code="CATEGORY_COMBINATION_INVALID", severity="blocking",
                field=child_key, related_fields=[parent_key],
                message="问题分类上下级组合无效，请按最新分类字典重新选择",
            ))

    start, end = _date(data.get("serviceCycleStart__c")), _date(data.get("serviceCycleEnd__c"))
    for key, label in (("serviceCycleStart__c", "周期服务开始时间"),
                       ("serviceCycleEnd__c", "周期服务结束时间"),
                       ("planFeedbackTime__c", "方案反馈时间"),
                       ("requireSolveTime__c", "要求解决时间")):
        if not _blank(data.get(key)) and _date(data.get(key)) is None:
            issues.append(ValidationIssue(
                code="INVALID_DATETIME", severity="blocking", field=key,
                message=f"{label}格式无效",
            ))
    if start and end and start > end:
        issues.append(ValidationIssue(
            code="SERVICE_PERIOD_INVALID", severity="blocking",
            field="serviceCycleEnd__c", related_fields=["serviceCycleStart__c"],
            message="周期服务结束时间不能早于开始时间",
        ))
    plan, solve = _date(data.get("planFeedbackTime__c")), _date(data.get("requireSolveTime__c"))
    if plan and solve and plan > solve:
        issues.append(ValidationIssue(
            code="FEEDBACK_AFTER_DEADLINE", severity="warning",
            field="planFeedbackTime__c", related_fields=["requireSolveTime__c"],
            message="方案反馈时间晚于要求解决时间，请核对",
        ))

    special_order = str(data.get("workOrderStatus__c") or "") in {
        str(v) for v in rules.get("special_order_types", [])
    }
    urgent = str(data.get("problemLevel__c") or "") in {
        str(v) for v in rules.get("urgent_problem_levels", ["2"])
    }
    if urgent or special_order:
        for key, label in (("problemResponsible__c", "问题责任人"),
                           ("problemDept__c", "问题责任部门"),
                           ("requireSolveTime__c", "要求解决时间")):
            if _blank(data.get(key)):
                issues.append(ValidationIssue(
                    code="SPECIAL_ORDER_FIELD_MISSING" if special_order else "URGENT_FIELD_MISSING",
                    severity="blocking", field=key,
                    related_fields=["workOrderStatus__c" if special_order else "problemLevel__c"],
                    message=f"特殊类型工单必须填写{label}" if special_order else f"重要紧急工单必须填写{label}",
                ))

    if str(data.get("needOnSite__c") or "") == "1":
        for key, label in (("stationName", "场站名称"), ("projectName__c", "项目名称")):
            if _blank(data.get(key)):
                issues.append(ValidationIssue(
                    code="ONSITE_CONTEXT_MISSING", severity="blocking", field=key,
                    related_fields=["needOnSite__c"], message=f"要求进场时必须填写{label}",
                ))
    if str(data.get("needCallBack__c") or "") == "1" and _blank(data.get("feedbackUserContact__c")):
        issues.append(ValidationIssue(
            code="CALLBACK_CONTACT_MISSING", severity="blocking",
            field="feedbackUserContact__c", related_fields=["needCallBack__c"],
            message="要求回电话时必须填写反馈人联系方式",
        ))

    description = str(data.get("caseDescription") or "").strip()
    if description and len(description) < 10:
        issues.append(ValidationIssue(
            code="DESCRIPTION_TOO_SHORT", severity="warning", field="caseDescription",
            message="工单描述过短，请确认故障现象、时间和影响范围是否完整",
        ))
    high_risk_category = str(data.get("problemType2__c") or "") in {
        str(v) for v in rules.get("high_risk_problem_type2", [])
    } or str(data.get("problemType3__c") or "") in {
        str(v) for v in rules.get("high_risk_problem_type3", [])
    }
    if (high_risk_category or any(k in description for k in rules.get("high_risk_keywords", []))) \
            and not urgent:
        issues.append(ValidationIssue(
            code="HIGH_RISK_KEYWORD", severity="warning", field="problemLevel__c",
            related_fields=["caseDescription"], message="描述包含高风险电力事件，请核对问题等级是否应为重要紧急",
        ))

    # 同一字段同一严重度只展示最具体的后一条规则，避免“通用必填+场景必填”重复提示。
    deduplicated = {(issue.severity, issue.field): issue for issue in issues}
    issues = list(deduplicated.values())
    blocking = sum(i.severity == "blocking" for i in issues)
    warning = sum(i.severity == "warning" for i in issues)
    return ValidationResult(valid=blocking == 0, blocking_count=blocking,
                            warning_count=warning, issues=issues)
