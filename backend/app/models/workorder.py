from sqlalchemy import Column, Integer, String, DateTime, Text

from .base import Base


class WorkOrder(Base):
    __tablename__ = "workorder"

    # NOTE: This model has 132+ existing fields which are omitted here for brevity.
    # The id column below is part of the existing schema and is included only
    # to satisfy SQLAlchemy's requirement for a primary key.
    id = Column(Integer, primary_key=True, autoincrement=True)

    # The following columns are newly added for the review/audit feature.
    version = Column(Integer, default=1, nullable=False)
    # NOTE: For MySQL 8.0 production with millisecond precision, use:
    # from sqlalchemy.dialects.mysql import DATETIME
    # reviewed_at = Column(DATETIME(fsp=3), nullable=True)
    # last_rejected_at = Column(DATETIME(fsp=3), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(64), nullable=True)
    reject_count = Column(Integer, default=0, nullable=False)
    last_reject_reason = Column(Text, nullable=True)
    last_rejected_by = Column(String(64), nullable=True)
    last_rejected_at = Column(DateTime, nullable=True)
