from sqlalchemy import Column, Integer, String, DateTime, Text

from .base import Base


class WorkOrder(Base):
    __tablename__ = "workorder"

    # NOTE: 此模型仅包含审核功能所需字段（约35列）。
    # 实际生产库 workorder 表有 132+ 列，其余列未在 ORM 模型中定义。
    # 执行 alembic revision --autogenerate 会检测到缺失列并生成 DROP COLUMN，
    # 生产环境迁移请务必使用手动编写的迁移脚本，而非 autogenerate。

    # Primary key
    id = Column(String(64), primary_key=True)

    # Review / audit tracking
    version = Column(Integer, default=1, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(64), nullable=True)
    reject_count = Column(Integer, default=0, nullable=False)
    last_reject_reason = Column(Text, nullable=True)
    last_rejected_by = Column(String(64), nullable=True)
    last_rejected_at = Column(DateTime, nullable=True)
    sync_status = Column(String(16), nullable=False, default='pending')
    # 'pending' | 'synced' | 'failed' — 销售易同步状态

    # Read-only metadata
    serial_number = Column(String(64), nullable=True)
    status = Column(String(32), nullable=True)
    created_at = Column(DateTime, nullable=True)
    initiator = Column(String(64), nullable=True)
    initiator_department = Column(String(128), nullable=True)

    # Editable fields (mapped to ALLOWED_FIELDS + frontend WorkOrderData)
    station_name = Column(String(255), nullable=True)
    dispatch_name = Column(String(255), nullable=True)
    project_code = Column(String(64), nullable=True)
    project_name = Column(String(255), nullable=True)
    project_province = Column(String(64), nullable=True)
    customer_name = Column(String(255), nullable=True)
    problem_description = Column(Text, nullable=True)
    feedback_channel = Column(String(64), nullable=True)
    product_line = Column(String(64), nullable=True)
    product_category = Column(String(64), nullable=True)
    product_type = Column(String(64), nullable=True)
    customer_level = Column(String(32), nullable=True)
    problem_category_l1 = Column(String(64), nullable=True)
    problem_category_l2 = Column(String(64), nullable=True)
    problem_category_l3 = Column(String(64), nullable=True)
    order_type = Column(String(32), nullable=True)
    problem_type = Column(String(64), nullable=True)
    fault_category = Column(String(64), nullable=True)
    fault_detail = Column(Text, nullable=True)
    responsible_person = Column(String(64), nullable=True)
    responsible_department = Column(String(128), nullable=True)
    primary_department = Column(String(128), nullable=True)
    after_sales_person = Column(String(64), nullable=True)
    transferred_person = Column(String(64), nullable=True)
    transferred_department = Column(String(128), nullable=True)
    order_level = Column(String(32), nullable=True)
    fault_level = Column(String(32), nullable=True)
    onsite_level = Column(String(32), nullable=True)
    required_solve_time = Column(String(64), nullable=True)
