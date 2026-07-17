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
