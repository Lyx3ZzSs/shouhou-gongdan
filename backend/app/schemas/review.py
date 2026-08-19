from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Any, Literal
from pydantic import Field

from app.services.review_validation import ValidationResult

from app.core.field_config import load_field_config

# ALLOWED_FIELDS 从 field_config.yaml 自动生成，排除只读/系统/隐藏字段
ALLOWED_FIELDS: set[str] = load_field_config().editable_keys

MAX_TEXT_FIELD_LENGTH = 5000


# ---- Shared validators ----

def _validate_reject_reason_not_empty(v: str | None) -> str | None:
    """驳回时 reject_reason 不为 None，且必须非空（含纯空格）。"""
    if v is not None and not v.strip():
        raise ValueError("驳回时必须填写审核备注")
    if v is not None and len(v) > MAX_TEXT_FIELD_LENGTH:
        raise ValueError(f"驳回原因不能超过 {MAX_TEXT_FIELD_LENGTH} 字符")
    return v


def _validate_review_notes_length(v: str | None) -> str | None:
    """审核备注长度限制。"""
    if v is not None and len(v) > MAX_TEXT_FIELD_LENGTH:
        raise ValueError(f"审核备注不能超过 {MAX_TEXT_FIELD_LENGTH} 字符")
    return v


class FieldChange(BaseModel):
    op: Literal["replace", "add", "remove"]
    path: str
    field_label: str
    old_value: Any | None = None
    new_value: Any | None = None

    @field_validator("path")
    @classmethod
    def path_must_start_with_slash(cls, v: str) -> str:
        if not v.startswith("/"):
            raise ValueError("path must start with '/'")
        return v

    @field_validator("new_value")
    @classmethod
    def remove_must_not_carry_value(cls, v: Any, info):
        if info.data.get("op") == "remove" and v is not None:
            raise ValueError("remove 操作的 new_value 必须为空")
        return v


class WorkOrderSummary(BaseModel):
    """Summary row for GET /api/workorders list."""
    id: str
    ticket_id: int
    name: str | None = None
    review_status: str | None = None
    caseAccountId: str | None = None
    projectName__c: str | None = None
    bigCustShortName__c: str | None = None
    caseDescription: str | None = None
    caseSource: str | None = None
    created_at: str | None = None

    @field_validator('created_at', mode='before')
    @classmethod
    def coerce_created_at(cls, v: datetime | str | None) -> str | None:
        return v.isoformat() if isinstance(v, datetime) else (str(v) if v is not None else None)

    model_config = ConfigDict(from_attributes=True)


class WorkOrderResponse(BaseModel):
    """Response for GET /api/workorders/{id} — merges ticket_view business fields + workorder_review metadata."""
    id: str
    version: int
    ticket_id: int
    review_status: str | None = None
    reject_count: int = 0
    last_reject_reason: str | None = None
    last_rejected_by: str | None = None
    last_rejected_at: str | None = None
    review_notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    initiator: str | None = None
    initiator_department: str | None = None
    field_overrides: dict | None = None
    original_data: dict[str, Any] | None = None
    validation: ValidationResult | None = None
    sync_status: str | None = None
    sync_external_id: str | None = None
    sync_last_error: str | None = None
    review_started_at: str | None = None
    review_duration_seconds: int | None = None
    reviewed_at: str | None = None
    reviewed_by: str | None = None

    # ---- 销售易 serviceCase API 业务字段 ----

    # Required fields
    ownerId: str | None = None
    dimDepart: str | None = None
    entityType: str | None = None
    name: str | None = None
    caseSource: str | None = None
    feedbackChannel__c: str | None = None
    workOrderStatus__c: str | None = None
    caseDescription: str | None = None
    caseStatus: str | None = None

    # Optional fields
    caseAccountId: str | None = None
    custLevel1__c: str | None = None
    projectName__c: str | None = None
    projectProvince__c: str | None = None
    bigCustShortName__c: str | None = None
    serviceCycleStart__c: str | None = None
    serviceCycleEnd__c: str | None = None
    isOfflineApply__c: str | None = None
    isOverdueService__c: str | None = None
    stationName: str | None = None
    problemLevel__c: str | None = None
    problemType1__c: str | None = None
    problemType2__c: str | None = None
    problemType3__c: str | None = None
    feedbackCount__c: str | None = None
    problemResponsible__c: str | None = None
    problemDept__c: str | None = None
    feedbackUserName__c: str | None = None
    feedbackUserContact__c: str | None = None
    needCallBack__c: str | None = None
    isHandled__c: str | None = None
    needOnSite__c: str | None = None
    remark__c: str | None = None
    relatedAttachment__c: str | None = None
    planFeedbackTime__c: str | None = None
    requireSolveTime__c: str | None = None

    # Hidden
    defectFlag__c: str | None = None

    @field_validator('created_at', 'last_rejected_at', 'reviewed_at', mode='before')
    @classmethod
    def coerce_datetime_fields(cls, v: datetime | str | None) -> str | None:
        return v.isoformat() if isinstance(v, datetime) else (str(v) if v is not None else None)

    model_config = ConfigDict(from_attributes=True)


class ReviewRequest(BaseModel):
    session_id: str
    version: int
    changes: list[FieldChange] = Field(default_factory=list)
    reject_reason: str | None = None
    review_notes: str | None = None
    lock_fencing_token: int

    _validate_reject_reason = field_validator("reject_reason")(_validate_reject_reason_not_empty)
    _validate_review_notes = field_validator("review_notes")(_validate_review_notes_length)


class ConfirmRequest(BaseModel):
    """确认提交请求 — 新增 idempotency_key 用于销售易幂等去重。"""
    session_id: str
    version: int
    changes: list[FieldChange] = Field(default_factory=list)
    reject_reason: str | None = None
    review_notes: str | None = None
    idempotency_key: str
    lock_fencing_token: int

    _validate_reject_reason = field_validator("reject_reason")(_validate_reject_reason_not_empty)
    _validate_review_notes = field_validator("review_notes")(_validate_review_notes_length)


class AuditLogEntry(BaseModel):
    session_id: str
    operator_name: str
    operated_at: str
    changes: list[FieldChange]


class ReviewResponse(BaseModel):
    review_id: str
    workorder_id: str
    status: Literal["confirmed", "rejected"]
    change_count: int
    bad_case_count: int
    next_review_status: str  # was: next_status


class ConfirmResponse(BaseModel):
    """确认提交响应。

    sync_status 始终为 "pending"：确认提交后由 BackgroundTasks 异步同步至销售易，
    实际同步结果（synced / failed）需通过 GET /api/admin/sync-failures 查询。
    """
    review_id: str
    workorder_id: str
    status: Literal["confirmed", "rejected"]
    change_count: int
    bad_case_count: int
    next_review_status: str  # was: next_status
    sync_status: Literal["pending", "syncing", "synced", "failed", "uncertain"] = "pending"


class StashRequest(BaseModel):
    """暂存请求 — 保存当前审核进度到服务端。

    mode='manual': 标记工单为 stashed，释放编辑锁。
    mode='auto_save': 仅保存进度，不改变工单状态，不释放锁。
    """
    field_states: dict[str, Any] = Field(default_factory=dict)  # fieldId → {currentValue, status, changeReason, ...}
    notes: str = ""
    mode: Literal["manual", "auto_save"] = "manual"
    lock_fencing_token: int
    _validate_notes = field_validator("notes")(_validate_review_notes_length)


class StashData(BaseModel):
    """Response for GET /api/workorders/{id}/stash"""
    field_states: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""
    updated_at: str | None = None


class StashResponse(BaseModel):
    status: str  # "ok"


class PaginatedWorkOrderSummary(BaseModel):
    """分页工单摘要列表。"""
    items: list[WorkOrderSummary]
    total: int
    offset: int
    limit: int


class NextWorkOrderResponse(BaseModel):
    """服务端领取的下一张待审核工单。"""
    workorder_id: str | None = None


class LockStatus(BaseModel):
    """Response for lock acquire / release / heartbeat endpoints."""
    locked: bool | None = None
    owner: str | None = None
    locked_minutes: int | None = None
    status: str | None = None
    fencing_token: int | None = None
