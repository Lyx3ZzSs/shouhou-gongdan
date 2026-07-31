"""fix bad_case_sample.source column size

Revision ID: 007_fix_source_size
Revises: 006_add_review_timing
Create Date: 2026-07-29

source 列原定义为 VARCHAR(16)，但默认值 'review_correction' 为 18 字符，
导致插入时 StringDataRightTruncationError。修复为 VARCHAR(32)。
"""
from typing import Sequence, Union
from alembic import op


revision: str = '007_fix_source_size'
down_revision: Union[str, Sequence[str], None] = '006_review_timing'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE bad_case_sample ALTER COLUMN source TYPE VARCHAR(32)")


def downgrade() -> None:
    op.execute("ALTER TABLE bad_case_sample ALTER COLUMN source TYPE VARCHAR(16)")
