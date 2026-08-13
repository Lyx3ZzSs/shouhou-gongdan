from sqlalchemy import Column, DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base


class ReviewSubmission(Base):
    __tablename__ = "review_submission"
    __table_args__ = (UniqueConstraint("workorder_id", "session_id", name="uq_submission_session"),)

    idempotency_key = Column(String(128), primary_key=True)
    workorder_id = Column(String(64), nullable=False, index=True)
    session_id = Column(String(64), nullable=False)
    decision = Column(String(16), nullable=False)
    request_hash = Column(String(64), nullable=False)
    response_data = Column(JSONB, nullable=False)
    operator_id = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
