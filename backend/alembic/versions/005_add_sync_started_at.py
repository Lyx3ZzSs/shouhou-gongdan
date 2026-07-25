"""add sync_started_at to workorder

Revision ID: 005_sync_started_at
Revises: 004_sync_idempotency
Create Date: 2026-07-25

为销售易同步超时判断新增一列：
- sync_started_at: 同步开始时间戳，recover_orphan_syncs 用于判断 syncing 是否超时（>30min）
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '005_sync_started_at'
down_revision: Union[str, Sequence[str], None] = '004_sync_idempotency'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workorder', sa.Column(
        'sync_started_at', sa.DateTime(timezone=True), nullable=True,
    ))


def downgrade() -> None:
    op.drop_column('workorder', 'sync_started_at')
