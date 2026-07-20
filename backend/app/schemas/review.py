from pydantic import BaseModel, field_validator
from typing import Any, Literal

ALLOWED_FIELDS = {
    "station_name", "dispatch_name", "project_code", "project_name",
    "project_province", "customer_name", "problem_description", "feedback_channel",
    "product_line", "product_category", "product_type", "customer_level",
    "problem_category_l1", "problem_category_l2", "problem_category_l3",
    "order_type", "problem_type", "fault_category", "fault_detail",
    "responsible_person", "responsible_department", "primary_department",
    "after_sales_person", "transferred_person", "transferred_department",
    "order_level", "fault_level", "onsite_level", "required_solve_time",
}

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


class WorkOrderSummary(BaseModel):
    """Summary row for GET /api/workorders list."""
    id: str
    serial_number: str | None = None
    station_name: str | None = None
    status: str | None = None
    customer_name: str | None = None
    created_at: str | None = None

    class Config:
        from_attributes = True


class WorkOrderResponse(BaseModel):
    """Response for GET /api/workorders/{id} — mirrors frontend WorkOrderData."""
    id: str
    version: int
    status: str | None = None
    reject_count: int = 0
    last_reject_reason: str | None = None
    last_rejected_by: str | None = None
    last_rejected_at: str | None = None
    review_notes: str | None = None
    serial_number: str | None = None
    created_at: str | None = None
    initiator: str | None = None
    initiator_department: str | None = None
    station_name: str | None = None
    dispatch_name: str | None = None
    project_code: str | None = None
    project_name: str | None = None
    project_province: str | None = None
    customer_name: str | None = None
    problem_description: str | None = None
    feedback_channel: str | None = None
    product_line: str | None = None
    product_category: str | None = None
    product_type: str | None = None
    customer_level: str | None = None
    problem_category_l1: str | None = None
    problem_category_l2: str | None = None
    problem_category_l3: str | None = None
    order_type: str | None = None
    problem_type: str | None = None
    fault_category: str | None = None
    fault_detail: str | None = None
    responsible_person: str | None = None
    responsible_department: str | None = None
    primary_department: str | None = None
    after_sales_person: str | None = None
    transferred_person: str | None = None
    transferred_department: str | None = None
    order_level: str | None = None
    fault_level: str | None = None
    onsite_level: str | None = None
    required_solve_time: str | None = None

    class Config:
        from_attributes = True


class ReviewRequest(BaseModel):
    session_id: str
    version: int
    changes: list[FieldChange] = []
    reject_reason: str | None = None
    review_notes: str | None = None

    _validate_reject_reason = field_validator("reject_reason")(_validate_reject_reason_not_empty)
    _validate_review_notes = field_validator("review_notes")(_validate_review_notes_length)


class ConfirmRequest(BaseModel):
    """确认提交请求 — 新增 idempotency_key 用于销售易幂等去重。"""
    session_id: str
    version: int
    changes: list[FieldChange] = []
    reject_reason: str | None = None
    review_notes: str | None = None
    idempotency_key: str

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
    next_status: str


class ConfirmResponse(BaseModel):
    """确认提交响应 — 新增 sync_status 表示销售易同步状态。"""
    review_id: str
    workorder_id: str
    status: Literal["confirmed", "rejected"]
    change_count: int
    bad_case_count: int
    next_status: str
    sync_status: Literal["pending", "synced", "failed"] = "pending"


class StashRequest(BaseModel):
    """暂存请求 — 保存当前审核进度到服务端。

    mode='manual': 标记工单为 stashed，释放编辑锁。
    mode='auto_save': 仅保存进度，不改变工单状态，不释放锁。
    """
    field_states: dict[str, Any] = {}  # fieldId → {currentValue, status, changeReason, ...}
    notes: str = ""
    mode: Literal["manual", "auto_save"] = "manual"
    _validate_notes = field_validator("notes")(_validate_review_notes_length)


class StashData(BaseModel):
    """Response for GET /api/workorders/{id}/stash"""
    field_states: dict[str, Any] = {}
    notes: str = ""
    updated_at: str | None = None


class StashResponse(BaseModel):
    status: str  # "ok"


class LockStatus(BaseModel):
    """Response for lock acquire / release / heartbeat endpoints."""
    locked: bool | None = None
    owner: str | None = None
    locked_minutes: int | None = None
    status: str | None = None
