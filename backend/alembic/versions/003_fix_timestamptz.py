"""fix timezone-aware columns: TIMESTAMP → TIMESTAMPTZ

Revision ID: 003_timestamptz
Revises: 002_servicecase
Create Date: 2026-07-24

Colunas operadas em audit_log e bad_case_sample tinham DateTime(timezone=False)
no modelo mas recebiam datetime.now(timezone.utc) (offset-aware). asyncpg pode
rejeitar a escrita de datetime aware em TIMESTAMP WITHOUT TIME ZONE.

Esta migração converte as colunas para TIMESTAMPTZ (TIMESTAMP WITH TIME ZONE).
"""
from typing import Sequence, Union
from alembic import op


revision: str = '003_timestamptz'
down_revision: Union[str, Sequence[str], None] = '002_servicecase'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # workorder_audit_log.operated_at
    op.execute("""
        ALTER TABLE workorder_audit_log
        ALTER COLUMN operated_at TYPE TIMESTAMPTZ
        USING operated_at AT TIME ZONE 'UTC'
    """)

    # bad_case_sample.created_at
    op.execute("""
        ALTER TABLE bad_case_sample
        ALTER COLUMN created_at TYPE TIMESTAMPTZ
        USING created_at AT TIME ZONE 'UTC'
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE workorder_audit_log
        ALTER COLUMN operated_at TYPE TIMESTAMP
        USING operated_at AT TIME ZONE 'UTC'
    """)
    op.execute("""
        ALTER TABLE bad_case_sample
        ALTER COLUMN created_at TYPE TIMESTAMP
        USING created_at AT TIME ZONE 'UTC'
    """)
