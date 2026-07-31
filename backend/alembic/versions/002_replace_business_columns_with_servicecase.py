"""replace mock business columns with 销售易 serviceCase API fields

Revision ID: 002_servicecase
Revises: 78a3d1c4f9e2
Create Date: 2026-07-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '002_servicecase'
down_revision: Union[str, Sequence[str], None] = '78a3d1c4f9e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_COLUMNS = [
    'station_name', 'dispatch_name', 'project_code', 'project_name',
    'project_province', 'customer_name', 'problem_description', 'feedback_channel',
    'product_line', 'product_category', 'product_type', 'customer_level',
    'problem_category_l1', 'problem_category_l2', 'problem_category_l3',
    'order_type', 'problem_type', 'fault_category', 'fault_detail',
    'responsible_person', 'responsible_department', 'primary_department',
    'after_sales_person', 'transferred_person', 'transferred_department',
    'order_level', 'fault_level', 'onsite_level', 'required_solve_time',
]

NEW_COLUMNS: list[tuple[str, type[sa.types.TypeEngine], str | None]] = [
    # Required fields
    ('ownerId', sa.String(64), None),
    ('dimDepart', sa.String(128), None),
    ('entityType', sa.String(32), '11010045500001'),
    ('name', sa.String(255), None),
    ('caseSource', sa.String(32), None),
    ('feedbackChannel__c', sa.String(32), None),
    ('workOrderStatus__c', sa.String(32), None),
    ('caseDescription', sa.Text(), None),
    ('caseStatus', sa.String(16), None),
    # Optional fields
    ('caseAccountId', sa.String(64), None),
    ('custLevel1__c', sa.String(32), None),
    ('projectName__c', sa.String(255), None),
    ('projectProvince__c', sa.String(64), None),
    ('bigCustShortName__c', sa.String(128), None),
    ('serviceCycleStart__c', sa.String(32), None),
    ('serviceCycleEnd__c', sa.String(32), None),
    ('isOfflineApply__c', sa.String(4), None),
    ('isOverdueService__c', sa.String(4), None),
    ('problemLevel__c', sa.String(32), None),
    ('problemType1__c', sa.String(32), None),
    ('problemType2__c', sa.String(64), None),
    ('problemType3__c', sa.String(64), None),
    ('feedbackCount__c', sa.String(16), None),
    ('problemResponsible__c', sa.String(64), None),
    ('problemDept__c', sa.String(128), None),
    ('feedbackUserName__c', sa.String(64), None),
    ('feedbackUserContact__c', sa.String(16), None),
    ('needCallBack__c', sa.String(4), None),
    ('isHandled__c', sa.String(4), None),
    ('needOnSite__c', sa.String(4), None),
    ('remark__c', sa.Text(), None),
    ('relatedAttachment__c', sa.String(255), None),
    ('planFeedbackTime__c', sa.String(32), None),
    ('requireSolveTime__c', sa.String(32), None),
    # Hidden
    ('defectFlag__c', sa.String(4), '1'),
]


def upgrade() -> None:
    for col in OLD_COLUMNS:
        op.drop_column('workorder', col)

    for col_name, col_type, default_val in NEW_COLUMNS:
        kwargs = {}
        if default_val is not None:
            kwargs['server_default'] = default_val
        op.add_column('workorder', sa.Column(col_name, col_type, nullable=True, **kwargs))


def downgrade() -> None:
    for col_name, _col_type, _default_val in reversed(NEW_COLUMNS):
        op.drop_column('workorder', col_name)

    # In downgrade, re-create old columns as plain nullable text—sufficient for rollback
    for col in OLD_COLUMNS:
        op.add_column('workorder', sa.Column(col, sa.Text(), nullable=True))
