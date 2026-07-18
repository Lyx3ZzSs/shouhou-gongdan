from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.auth.dependencies import get_current_user, CurrentUser
from app.schemas.review import ReviewRequest, ReviewResponse, WorkOrderResponse, WorkOrderSummary, AuditLogEntry, FieldChange
from app.services.review_service import ReviewService
from app.core.database import get_db
from app.models.audit_log import WorkOrderAuditLog
from app.models.workorder import WorkOrder

router = APIRouter(prefix="/api/workorders", tags=["review"])


@router.get("", response_model=list[WorkOrderSummary])
async def list_workorders(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WorkOrder)
        .where(WorkOrder.created_at.isnot(None))
        .order_by(WorkOrder.created_at.desc())
        .limit(50)
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


@router.get("/{workorder_id}", response_model=WorkOrderResponse)
async def get_workorder(
    workorder_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        wid = int(workorder_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="工单ID必须为数字")
    result = await db.execute(
        select(WorkOrder).where(WorkOrder.id == wid)
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
        ai_confidence=float(wo.ai_confidence) if wo.ai_confidence is not None else None,
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


@router.post("/{workorder_id}/review", response_model=ReviewResponse)
async def review_workorder(
    workorder_id: str,
    request: ReviewRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ReviewService(db)
    result = await service.review(
        workorder_id=workorder_id,
        request=request,
        operator_id=current_user.user_id,
        operator_name=current_user.name,
        operator_department=current_user.department,
    )
    return ReviewResponse(**result)


@router.get("/{workorder_id}/audit-logs", response_model=list[AuditLogEntry])
async def get_audit_logs(
    workorder_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WorkOrderAuditLog)
        .where(WorkOrderAuditLog.workorder_id == workorder_id)
        .order_by(WorkOrderAuditLog.operated_at.desc())
    )
    rows = result.scalars().all()

    sessions = {}
    for row in rows:
        sid = row.session_id
        if sid not in sessions:
            sessions[sid] = {
                "session_id": sid,
                "operator_name": row.operator_name,
                "operated_at": row.operated_at.isoformat(),
                "changes": [],
            }
        sessions[sid]["changes"].append({
            "op": row.change_type,
            "path": row.field_path,
            "field_label": row.field_label,
            "old_value": row.old_value,
            "new_value": row.new_value,
            "ai_confidence": float(row.ai_confidence) if row.ai_confidence is not None else None,
        })

    return list(sessions.values())
