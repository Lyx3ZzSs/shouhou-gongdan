"""add sync_attempts and sync_last_error columns to workorder

Revision ID: 78a3d1c4f9e2
Revises: 56d2d0502907
Create Date: 2026-07-23

销售易后台同步重试追踪所需的新列：
- sync_attempts: 当前确认周期的同步尝试次数（默认 0）
- sync_last_error: 最近一次同步失败的错误信息（可为 NULL）
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '78a3d1c4f9e2'
down_revision: Union[str, None] = '56d2d0502907'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'workorder',
        sa.Column('sync_attempts', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'workorder',
        sa.Column('sync_last_error', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('workorder', 'sync_last_error')
    op.drop_column('workorder', 'sync_attempts')
