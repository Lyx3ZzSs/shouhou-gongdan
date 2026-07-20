from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update as sa_update, delete as sa_delete, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.auth.dependencies import get_current_user, CurrentUser
from app.models.workorder import WorkOrder
from app.models.workorder_stash import WorkOrderStash
from app.services.lock_service import get_lock_service
from app.schemas.review import (
    ReviewRequest, ReviewResponse,
    ConfirmRequest, ConfirmResponse,
    WorkOrderResponse, WorkOrderSummary, AuditLogEntry,
    StashRequest, StashResponse, StashData,
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
    """暂存审核进度。

    mode='manual': 标记工单为 stashed + 释放锁，其他人可接手。
    mode='auto_save': 仅保存进度，不改变工单状态，不释放锁。
    """
    lock_service = get_lock_service()
    owner = await lock_service.get_owner(workorder_id)
    if owner is None or owner["operator_id"] != current_user.user_id:
        raise HTTPException(status_code=423, detail="请先获取编辑锁")

    async with db.begin():
        # Upsert stash data
        stmt = pg_insert(WorkOrderStash).values(
            workorder_id=workorder_id,
            field_states=request.field_states,
            notes=request.notes,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=['workorder_id'],
            set_=dict(
                field_states=stmt.excluded.field_states,
                notes=stmt.excluded.notes,
                updated_at=func.now(),
            ),
        )
        await db.execute(stmt)

        if request.mode == "manual":
            await db.execute(
                sa_update(WorkOrder)
                .where(WorkOrder.id == workorder_id)
                .values(status='stashed')
            )

    if request.mode == "manual":
        # Release lock so others can pick up the ticket
        svc = ReviewService(db)
        await svc.release_lock_safely(workorder_id, current_user.user_id)

    return {"status": "ok"}


@router.get("/{workorder_id}/stash", response_model=StashData)
async def get_stash(
    workorder_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取暂存的审核进度。404 表示无暂存数据。"""
    result = await db.execute(
        select(WorkOrderStash).where(WorkOrderStash.workorder_id == workorder_id)
    )
    stash = result.scalar_one_or_none()
    if stash is None:
        raise HTTPException(status_code=404, detail="暂存数据不存在")

    return StashData(
        field_states=stash.field_states,
        notes=stash.notes or "",
        updated_at=stash.updated_at.isoformat() if stash.updated_at else None,
    )


@router.delete("/{workorder_id}/stash", response_model=StashResponse)
async def delete_stash(
    workorder_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除暂存的审核进度（用户丢弃修改时调用）。"""
    lock_service = get_lock_service()
    owner = await lock_service.get_owner(workorder_id)
    if owner is None or owner["operator_id"] != current_user.user_id:
        raise HTTPException(status_code=423, detail="请先获取编辑锁")

    async with db.begin():
        svc = ReviewService(db)
        await svc.delete_stash(workorder_id)
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
