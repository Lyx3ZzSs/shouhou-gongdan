"""add workorder_stash table

Revision ID: 02239b2cf35d
Revises: b36e5bd808d6
Create Date: 2026-07-20 11:33:44.392475

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '02239b2cf35d'
down_revision: Union[str, Sequence[str], None] = 'b36e5bd808d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('workorder_stash',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('workorder_id', sa.String(length=64), nullable=False),
        sa.Column('field_states', JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('notes', sa.Text(), nullable=True, server_default=sa.text("''")),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workorder_id', name='uq_workorder_stash_workorder_id'),
    )
    op.create_index('idx_workorder_stash_workorder_id', 'workorder_stash', ['workorder_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_workorder_stash_workorder_id', table_name='workorder_stash')
    op.drop_table('workorder_stash')
