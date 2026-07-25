"""add sync_idempotency_key and sync_external_id to workorder

Revision ID: 004_sync_idempotency
Revises: 003_timestamptz
Create Date: 2026-07-24

为销售易同步幂等性新增两列：
- sync_idempotency_key: 同一次确认提交的多次同步尝试共享同一 key
- sync_external_id: 销售易返回的工单 ID，非空时表示幂等已完成
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '004_sync_idempotency'
down_revision: Union[str, Sequence[str], None] = '003_timestamptz'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workorder', sa.Column(
        'sync_idempotency_key', sa.String(128), nullable=True,
    ))
    op.add_column('workorder', sa.Column(
        'sync_external_id', sa.String(64), nullable=True,
    ))
    op.create_index(
        'idx_sync_external_id', 'workorder', ['sync_external_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('idx_sync_external_id', table_name='workorder')
    op.drop_column('workorder', 'sync_external_id')
    op.drop_column('workorder', 'sync_idempotency_key')
