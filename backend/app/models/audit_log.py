from sqlalchemy import Column, BigInteger, String, Text, DateTime, Index
from datetime import datetime, timezone

from .base import Base


class WorkOrderAuditLog(Base):
    __tablename__ = "workorder_audit_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    workorder_id = Column(String(64), nullable=False)
    session_id = Column(String(64), nullable=False)
    field_path = Column(String(128), nullable=False)
    field_label = Column(String(64), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    change_type = Column(String(16), nullable=False, default="replace")
    operator_id = Column(String(64), nullable=False)
    operator_name = Column(String(64), nullable=True)
    # PostgreSQL TIMESTAMP is sufficient for development and production use.
    operated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_workorder", "workorder_id"),
        Index("idx_session", "session_id"),
        Index("idx_operator", "operator_id"),
        Index("idx_operated_at", "operated_at"),
    )
