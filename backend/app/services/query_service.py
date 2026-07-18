"""只读查询服务 — 将读路径 SQL 从 router 中抽离。"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.models.workorder import WorkOrder
from app.schemas.review import WorkOrderSummary, WorkOrderResponse


class WorkOrderQueryService:
    """工单只读查询。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_summaries(self, limit: int = 50) -> list[WorkOrderSummary]:
        """返回工单摘要列表（按创建时间倒序）。"""
        result = await self.db.execute(
            select(WorkOrder)
            .where(WorkOrder.created_at.isnot(None))
            .order_by(WorkOrder.created_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [
            WorkOrderSummary(
                id=str(wo.id),
                serial_number=wo.serial_number,
                station_name=wo.station_name,
                status=wo.status,
                customer_name=wo.customer_name,
                created_at=wo.created_at.isoformat() if wo.created_at else None,
            )
            for wo in rows
        ]

    async def get_detail(self, workorder_id: str) -> WorkOrderResponse:
        """返回单个工单完整详情。"""
        result = await self.db.execute(
            select(WorkOrder).where(WorkOrder.id == workorder_id)
        )
        wo = result.scalar_one_or_none()
        if wo is None:
            raise HTTPException(status_code=404, detail="工单不存在")

        return WorkOrderResponse(
            id=str(wo.id),
            version=wo.version,
            status=wo.status,
            reject_count=wo.reject_count,
            last_reject_reason=wo.last_reject_reason,
            last_rejected_by=wo.last_rejected_by,
            last_rejected_at=wo.last_rejected_at.isoformat() if wo.last_rejected_at else None,
            serial_number=wo.serial_number,
            created_at=wo.created_at.isoformat() if wo.created_at else None,
            initiator=wo.initiator,
            initiator_department=wo.initiator_department,
            station_name=wo.station_name,
            dispatch_name=wo.dispatch_name,
            project_code=wo.project_code,
            project_name=wo.project_name,
            project_province=wo.project_province,
            customer_name=wo.customer_name,
            problem_description=wo.problem_description,
            feedback_channel=wo.feedback_channel,
            product_line=wo.product_line,
            product_category=wo.product_category,
            product_type=wo.product_type,
            customer_level=wo.customer_level,
            problem_category_l1=wo.problem_category_l1,
            problem_category_l2=wo.problem_category_l2,
            problem_category_l3=wo.problem_category_l3,
            order_type=wo.order_type,
            problem_type=wo.problem_type,
            fault_category=wo.fault_category,
            fault_detail=wo.fault_detail,
            responsible_person=wo.responsible_person,
            responsible_department=wo.responsible_department,
            primary_department=wo.primary_department,
            after_sales_person=wo.after_sales_person,
            transferred_person=wo.transferred_person,
            transferred_department=wo.transferred_department,
            order_level=wo.order_level,
            fault_level=wo.fault_level,
            onsite_level=wo.onsite_level,
            required_solve_time=wo.required_solve_time,
        )
