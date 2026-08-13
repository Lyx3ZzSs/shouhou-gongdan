"""只读查询服务 — JOIN workorder_review + ticket_view 获取完整工单数据。"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException

from app.models.workorder import WorkOrderReview
from app.models.ticket import TicketView
from app.schemas.review import WorkOrderSummary, WorkOrderResponse, PaginatedWorkOrderSummary
from app.services.review_validation import validate_workorder


class WorkOrderQueryService:
    """工单只读查询。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _build_filters(review_status: str | None = None, keyword: str | None = None):
        """构建动态 WHERE 条件列表。"""
        filters = [WorkOrderReview.created_at.isnot(None)]
        if review_status:
            filters.append(WorkOrderReview.review_status == review_status)
        if keyword:
            sanitized = keyword.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            kw = f"%{sanitized}%"
            filt = (
                WorkOrderReview.ticket_no.ilike(kw, escape='\\')
            )
            # Also search ticket_view by joining (handled in list_summaries)
            filters.append(filt)
        return filters

    async def list_summaries(
        self,
        status: str | None = None,
        keyword: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> PaginatedWorkOrderSummary:
        """返回分页工单摘要列表（JOIN ticket_view，LEFT JOIN 防孤儿记录）。"""
        # 使用 status 参数作为 review_status
        review_status = status

        # Build the query with LEFT JOIN to ticket_view
        base_query = (
            select(
                WorkOrderReview.id,
                WorkOrderReview.ticket_no,
                WorkOrderReview.review_status,
                WorkOrderReview.reject_count,
                func.coalesce(TicketView.source_created_at, WorkOrderReview.created_at).label("created_at"),
                TicketView.name,
                TicketView.caseDescription,
                TicketView.caseAccountId,
                TicketView.projectName__c,
                TicketView.caseStatus,
                TicketView.caseSource,
                TicketView.workOrderStatus__c,
                TicketView.problemLevel__c,
                TicketView.bigCustShortName__c,
            )
            .select_from(WorkOrderReview)
            .outerjoin(TicketView, WorkOrderReview.ticket_no == TicketView.ticket_no)
        )

        # Apply filters
        if review_status:
            base_query = base_query.where(WorkOrderReview.review_status == review_status)
        if keyword:
            sanitized = keyword.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            kw = f"%{sanitized}%"
            base_query = base_query.where(
                (WorkOrderReview.ticket_no.ilike(kw, escape='\\')) |
                (TicketView.name.ilike(kw, escape='\\')) |
                (TicketView.caseAccountId.ilike(kw, escape='\\')) |
                (TicketView.projectName__c.ilike(kw, escape='\\'))
            )

        # Count total
        count_query = (
            select(func.count())
            .select_from(WorkOrderReview)
            .outerjoin(TicketView, WorkOrderReview.ticket_no == TicketView.ticket_no)
        )
        if review_status:
            count_query = count_query.where(WorkOrderReview.review_status == review_status)
        if keyword:
            count_query = count_query.where(
                (WorkOrderReview.ticket_no.ilike(kw, escape='\\')) |
                (TicketView.name.ilike(kw, escape='\\')) |
                (TicketView.caseAccountId.ilike(kw, escape='\\')) |
                (TicketView.projectName__c.ilike(kw, escape='\\'))
            )
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Fetch page
        result = await self.db.execute(
            base_query
            .order_by(WorkOrderReview.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = result.mappings().all()

        items = []
        for row in rows:
            items.append(WorkOrderSummary(
                id=row["id"],
                ticket_no=row["ticket_no"],
                name=row["name"],
                review_status=row["review_status"],
                caseAccountId=row["caseAccountId"],
                bigCustShortName__c=row["bigCustShortName__c"],
                created_at=row["created_at"],
            ))

        return PaginatedWorkOrderSummary(
            items=items,
            total=total,
            offset=offset,
            limit=limit,
        )

    async def get_detail(self, workorder_id: str) -> WorkOrderResponse:
        """返回单个工单完整详情（merge workorder_review + ticket_view + field_overrides）。"""
        # Get review record
        result = await self.db.execute(
            select(WorkOrderReview).where(WorkOrderReview.id == workorder_id)
        )
        review = result.scalar_one_or_none()
        if review is None:
            raise HTTPException(status_code=404, detail="工单不存在")

        # Get ticket_view data
        ticket_result = await self.db.execute(
            select(TicketView).where(TicketView.ticket_no == review.ticket_no)
        )
        ticket = ticket_result.scalar_one_or_none()

        # Build response: start with review metadata
        resp_dict = {
            "id": review.id,
            "version": review.version,
            "ticket_no": review.ticket_no,
            "review_status": review.review_status,
            "reject_count": review.reject_count,
            "last_reject_reason": review.last_reject_reason,
            "last_rejected_by": review.last_rejected_by,
            "last_rejected_at": review.last_rejected_at,
            "review_notes": review.review_notes,
            "created_at": review.created_at.isoformat() if review.created_at else None,
            "updated_at": review.updated_at.isoformat() if review.updated_at else None,
            "initiator": review.initiator,
            "initiator_department": review.initiator_department,
            "field_overrides": review.field_overrides,
            "sync_status": review.sync_status,
            "sync_external_id": review.sync_external_id,
            "sync_last_error": review.sync_last_error,
            "review_started_at": review.review_started_at.isoformat() if review.review_started_at else None,
            "review_duration_seconds": review.review_duration_seconds,
        }

        # Merge ticket_view business fields
        original_data = {}
        if ticket is not None:
            ticket_dict = ticket.to_dict()
            # Remove id and ticket_no from ticket dict (already in review metadata)
            ticket_dict.pop("id", None)
            ticket_dict.pop("ticket_no", None)
            source_created_at = ticket_dict.pop("source_created_at", None)
            if source_created_at is not None:
                resp_dict["created_at"] = source_created_at.isoformat()
            original_data = dict(ticket_dict)
            current_data = {**ticket_dict, **(review.field_overrides or {})}
            resp_dict.update(current_data)

        resp_dict["original_data"] = original_data
        resp_dict["validation"] = validate_workorder(resp_dict)

        return WorkOrderResponse(**resp_dict)
