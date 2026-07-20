from sqlalchemy import Column, BigInteger, String, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from .base import Base


class WorkOrderStash(Base):
    """暂存审核进度 — 保存人工编辑的字段状态和备注。

    一个工单最多一条暂存记录（workorder_id UNIQUE），
    每次暂存/自动保存 upsert 覆盖。
    """

    __tablename__ = "workorder_stash"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    workorder_id = Column(String(64), nullable=False, unique=True, index=True)
    field_states = Column(JSONB, nullable=False, default=dict)
    notes = Column(Text, nullable=True, default="")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
