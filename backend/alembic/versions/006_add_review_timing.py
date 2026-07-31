"""add review_started_at and review_duration_seconds to workorder

Revision ID: 006_review_timing
Revises: 005_sync_started_at
Create Date: 2026-07-25

为审核操作计时新增两列：
- review_started_at: 审核开始时间（锁首次获取时记录）
- review_duration_seconds: 审核耗时（秒），确认/驳回时计算
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '006_review_timing'
down_revision: Union[str, Sequence[str], None] = '005_sync_started_at'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workorder', sa.Column(
        'review_started_at', sa.DateTime(timezone=True), nullable=True,
    ))
    op.add_column('workorder', sa.Column(
        'review_duration_seconds', sa.Integer(), nullable=True,
    ))


def downgrade() -> None:
    op.drop_column('workorder', 'review_duration_seconds')
    op.drop_column('workorder', 'review_started_at')
