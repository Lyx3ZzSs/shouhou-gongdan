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


class FieldChange(BaseModel):
    op: Literal["replace", "add", "remove"]
    path: str
    field_label: str
    old_value: Any | None = None
    new_value: Any | None = None
    ai_confidence: float | None = None

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
    ai_confidence: float | None = None
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


class LockStatus(BaseModel):
    """Response for lock acquire / release / heartbeat endpoints."""
    locked: bool | None = None
    owner: str | None = None
    locked_minutes: int | None = None
    status: str | None = None
