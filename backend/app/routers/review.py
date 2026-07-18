from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update as sa_update
from app.auth.dependencies import get_current_user, CurrentUser
from app.models.workorder import WorkOrder
from app.services.lock_service import get_lock_service
from app.schemas.review import (
    ReviewRequest, ReviewResponse,
    ConfirmRequest, ConfirmResponse,
    WorkOrderResponse, WorkOrderSummary, AuditLogEntry,
    StashRequest, StashResponse,
)
from app.services.review_service import ReviewService
from app.services.query_service import WorkOrderQueryService
from app.core.database import get_db
from app.models.audit_log import WorkOrderAuditLog

router = APIRouter(prefix="/api/workorders", tags=["review"])


@router.get("", response_model=list[WorkOrderSummary])
async def list_workorders(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await WorkOrderQueryService(db).list_summaries()


@router.get("/{workorder_id}", response_model=WorkOrderResponse)
async def get_workorder(
    workorder_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await WorkOrderQueryService(db).get_detail(workorder_id)


@router.post("/{workorder_id}/review", response_model=ReviewResponse)
async def review_workorder(
    workorder_id: str,
    request: ReviewRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lock_service = get_lock_service()
    owner = await lock_service.get_owner(workorder_id)
    if owner is None or owner["operator_id"] != current_user.user_id:
        raise HTTPException(status_code=423, detail="请先获取编辑锁")

    service = ReviewService(db)
    result = await service.review(
        workorder_id=workorder_id,
        request=request,
        operator_id=current_user.user_id,
        operator_name=current_user.name,
        operator_department=current_user.department,
    )
    return ReviewResponse(**result)


@router.post("/{workorder_id}/confirm", response_model=ConfirmResponse)
async def confirm_workorder(
    workorder_id: str,
    request: ConfirmRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """确认提交：审核通过后本地落库，后台异步同步至销售易。"""
    lock_service = get_lock_service()
    owner = await lock_service.get_owner(workorder_id)
    if owner is None or owner["operator_id"] != current_user.user_id:
        raise HTTPException(status_code=423, detail="请先获取编辑锁")

    service = ReviewService(db)
    result = await service.confirm(
        workorder_id=workorder_id,
        request=request,
        operator_id=current_user.user_id,
        operator_name=current_user.name,
        operator_department=current_user.department,
    )
    return ConfirmResponse(**result)


@router.post("/{workorder_id}/stash", response_model=StashResponse)
async def stash_workorder(
    workorder_id: str,
    request: StashRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """暂存审核进度：仅保存状态标记（status='stashed'）。"""
    lock_service = get_lock_service()
    owner = await lock_service.get_owner(workorder_id)
    if owner is None or owner["operator_id"] != current_user.user_id:
        raise HTTPException(status_code=423, detail="请先获取编辑锁")

    await db.execute(
        sa_update(WorkOrder)
        .where(WorkOrder.id == workorder_id)
        .values(status='stashed')
    )
    await db.commit()
    return {"status": "ok"}


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
        })

    return list(sessions.values())
