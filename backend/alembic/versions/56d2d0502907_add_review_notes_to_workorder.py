"""add review_notes column to workorder

Revision ID: 56d2d0502907
Revises: 02239b2cf35d
Create Date: 2026-07-20 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '56d2d0502907'
down_revision: Union[str, Sequence[str], None] = '02239b2cf35d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use raw SQL with IF NOT EXISTS to avoid conflicts when schema_init.sql
    # has already been applied (e.g. fresh DB provisioning).
    op.execute(
        "ALTER TABLE workorder ADD COLUMN IF NOT EXISTS review_notes TEXT"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE workorder DROP COLUMN IF EXISTS review_notes"
    )
