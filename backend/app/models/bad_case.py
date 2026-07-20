from sqlalchemy import Column, BigInteger, String, Text, DateTime, ForeignKey, Index
from datetime import datetime

from .base import Base


class BadCaseSample(Base):
    __tablename__ = "bad_case_sample"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    workorder_id = Column(String(64), nullable=False)
    audit_log_id = Column(BigInteger, ForeignKey("workorder_audit_log.id"), nullable=False)
    field_path = Column(String(128), nullable=False)
    ai_value = Column(Text, nullable=True)
    human_value = Column(Text, nullable=True)
    sample_status = Column(String(16), nullable=False, default="pending")
    source = Column(String(16), nullable=False, default="review_correction")
    # PostgreSQL TIMESTAMP is sufficient for development and production use.
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_status", "sample_status"),
        Index("idx_workorder", "workorder_id"),
    )
