from sqlalchemy import BigInteger, Column, Integer, String, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import Base


class WorkOrderReview(Base):
    """审核元数据表 — 仅包含审核/同步相关列，业务数据通过 ticket_view 视图获取。"""

    __tablename__ = "workorder_review"

    # Primary key
    id = Column(String(64), primary_key=True)

    # FK to ticket (via ticket_no, not DB FK)
    ticket_no = Column(String(100), nullable=False, unique=True)

    # Optimistic locking
    version = Column(Integer, default=1, nullable=False)
    lock_fencing_token = Column(BigInteger, default=0, nullable=False)

    # Review status
    review_status = Column(String(32), nullable=False, default='pending_review')
    # pending_review | reviewing | confirmed | returned | stashed

    # Review result
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(64), nullable=True)
    reject_count = Column(Integer, default=0, nullable=False)
    last_reject_reason = Column(Text, nullable=True)
    last_rejected_by = Column(String(64), nullable=True)
    last_rejected_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)

    # Review timing
    review_started_at = Column(DateTime(timezone=True), nullable=True)
    review_duration_seconds = Column(Integer, nullable=True)

    # Review edits (JSONB overrides over ticket_view values)
    field_overrides = Column(JSONB, nullable=False, default=dict)

    # Sync to 销售易
    sync_status = Column(String(16), nullable=False, default='pending')
    sync_attempts = Column(Integer, nullable=False, default=0)
    sync_last_error = Column(Text, nullable=True)
    sync_idempotency_key = Column(String(128), nullable=True)
    sync_external_id = Column(String(64), nullable=True)
    sync_started_at = Column(DateTime(timezone=True), nullable=True)

    # Initiator info (denormalized from ticket at import time)
    initiator = Column(String(64), nullable=True)
    initiator_department = Column(String(128), nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    # ORM relationships
    audit_logs = relationship(
        "WorkOrderAuditLog", lazy="raise",
        primaryjoin="WorkOrderReview.id == foreign(WorkOrderAuditLog.workorder_id)",
    )
    stash = relationship(
        "WorkOrderStash", lazy="raise", uselist=False,
        primaryjoin="WorkOrderReview.id == foreign(WorkOrderStash.workorder_id)",
    )
    bad_cases = relationship(
        "BadCaseSample", lazy="raise",
        primaryjoin="WorkOrderReview.id == foreign(BadCaseSample.workorder_id)",
    )
