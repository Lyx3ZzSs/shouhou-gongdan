"""只读查询服务 — 将读路径 SQL 从 router 中抽离。"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException

from app.models.workorder import WorkOrder
from app.schemas.review import WorkOrderSummary, WorkOrderResponse, PaginatedWorkOrderSummary


class WorkOrderQueryService:
    """工单只读查询。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _build_filters(status: str | None = None, keyword: str | None = None):
        """构建动态 WHERE 条件列表。"""
        filters = [WorkOrder.created_at.isnot(None)]
        if status:
            filters.append(WorkOrder.status == status)
        if keyword:
            # 转义 LIKE 通配符 % 和 _，防止搜索结果出人意料
            sanitized = keyword.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            kw = f"%{sanitized}%"
            filters.append(
                (WorkOrder.serial_number.ilike(kw, escape='\\')) |
                (WorkOrder.name.ilike(kw, escape='\\')) |
                (WorkOrder.caseAccountId.ilike(kw, escape='\\')) |
                (WorkOrder.projectName__c.ilike(kw, escape='\\'))
            )
        return filters

    async def list_summaries(
        self,
        status: str | None = None,
        keyword: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> PaginatedWorkOrderSummary:
        """返回分页工单摘要列表（支持状态筛选和关键词搜索，按创建时间倒序）。"""
        filters = self._build_filters(status, keyword)

        # Count total
        total_result = await self.db.execute(
            select(func.count()).select_from(WorkOrder).where(*filters)
        )
        total = total_result.scalar() or 0

        # Fetch page
        result = await self.db.execute(
            select(WorkOrder)
            .where(*filters)
            .order_by(WorkOrder.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = result.scalars().all()

        return PaginatedWorkOrderSummary(
            items=[WorkOrderSummary.model_validate(wo) for wo in rows],
            total=total,
            offset=offset,
            limit=limit,
        )

    async def get_detail(self, workorder_id: str) -> WorkOrderResponse:
        """返回单个工单完整详情。"""
        result = await self.db.execute(
            select(WorkOrder).where(WorkOrder.id == workorder_id)
        )
        wo = result.scalar_one_or_none()
        if wo is None:
            raise HTTPException(status_code=404, detail="工单不存在")

        return WorkOrderResponse.model_validate(wo)
