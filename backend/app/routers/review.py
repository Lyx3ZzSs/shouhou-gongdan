import uuid
from pydantic import BaseModel, Field
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update as sa_update, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.auth.dependencies import require_admin, require_any_role
from app.auth.schemas import CurrentUser
from app.models.workorder import WorkOrderReview
from app.models.workorder_stash import WorkOrderStash
from app.services.lock_service import get_lock_service
from app.schemas.review import (
    ReviewRequest, ReviewResponse,
    ConfirmRequest, ConfirmResponse,
    WorkOrderResponse, AuditLogEntry,
    StashRequest, StashResponse, StashData,
    PaginatedWorkOrderSummary,
)
from app.services.review_service import ReviewService, background_sync_to_xiaoshouyi
from app.services.query_service import WorkOrderQueryService
from app.services.import_service import import_workorders
from app.core.database import get_db, async_session
from app.models.audit_log import WorkOrderAuditLog

router = APIRouter(prefix="/api/workorders", tags=["review"])


@router.get("", response_model=PaginatedWorkOrderSummary)
async def list_workorders(
    status: str | None = None,
    keyword: str | None = None,
    offset: int = 0,
    limit: int = 50,
    current_user: CurrentUser = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """工单列表（分页 + 搜索）。

    - status: 按工单状态筛选（pending_review / confirmed / stashed）
    - keyword: 按序列号/站点/客户/项目名模糊搜索
    - offset/limit: 分页参数（默认每页 50 条）
    """
    return await WorkOrderQueryService(db).list_summaries(
        status=status, keyword=keyword, offset=offset, limit=limit,
    )


@router.get("/{workorder_id}", response_model=WorkOrderResponse)
async def get_workorder(
    workorder_id: str,
    current_user: CurrentUser = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    return await WorkOrderQueryService(db).get_detail(workorder_id)


@router.post(
    "/{workorder_id}/review",
    response_model=ReviewResponse,
    deprecated=True,
)
async def review_workorder(
    workorder_id: str,
    request: ReviewRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """[已废弃] 请使用 POST /{workorder_id}/confirm 代替。

    本端点仍可正常使用，但将在未来版本中移除。
    """
    lock_service = get_lock_service()
    owner = await lock_service.get_owner(workorder_id)
    if (owner is None or owner["operator_id"] != current_user.user_id
            or owner.get("fencing_token") != request.lock_fencing_token):
        raise HTTPException(status_code=423, detail="请先获取编辑锁")

    service = ReviewService(db)
    result = await service.review(
        workorder_id=workorder_id,
        request=request,
        operator_id=current_user.user_id,
        operator_name=current_user.display_name,
        operator_department=current_user.department_code,
    )
    # review() 现已委托给 confirm()，同样支持后台同步
    if result.sync_idempotency_key is not None:
        background_tasks.add_task(
            background_sync_to_xiaoshouyi,
            workorder_id,
            result.sync_idempotency_key,
            async_session,
        )
    return ReviewResponse(**result.response)


@router.post("/{workorder_id}/confirm", response_model=ConfirmResponse)
async def confirm_workorder(
    workorder_id: str,
    request: ConfirmRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """确认提交：本地落库后立即返回，后台异步同步至销售易。"""
    service = ReviewService(db)
    existing = await service.get_idempotent_response(workorder_id, request)
    if existing is not None:
        return ConfirmResponse(**existing)
    await db.rollback()

    lock_service = get_lock_service()
    owner = await lock_service.get_owner(workorder_id)
    if (owner is None or owner["operator_id"] != current_user.user_id
            or owner.get("fencing_token") != request.lock_fencing_token):
        raise HTTPException(status_code=423, detail="请先获取编辑锁")

    result = await service.confirm(
        workorder_id=workorder_id,
        request=request,
        operator_id=current_user.user_id,
        operator_name=current_user.display_name,
        operator_department=current_user.department_code,
    )

    # 调度后台同步（在 HTTP 响应返回后执行）
    if result.sync_idempotency_key is not None:
        background_tasks.add_task(
            background_sync_to_xiaoshouyi,
            workorder_id,
            result.sync_idempotency_key,
            async_session,
        )

    return ConfirmResponse(**result.response)


@router.post("/{workorder_id}/stash", response_model=StashResponse)
async def stash_workorder(
    workorder_id: str,
    request: StashRequest,
    current_user: CurrentUser = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """暂存审核进度。

    mode='manual': 标记工单为 stashed + 释放锁，其他人可接手。
    mode='auto_save': 仅保存进度，不改变工单状态，不释放锁。
    """
    lock_service = get_lock_service()
    owner = await lock_service.get_owner(workorder_id)
    if (owner is None or owner["operator_id"] != current_user.user_id
            or owner.get("fencing_token") != request.lock_fencing_token):
        raise HTTPException(status_code=423, detail="请先获取编辑锁")

    async with db.begin():
        status_row = await db.execute(
            select(WorkOrderReview.review_status).where(WorkOrderReview.id == workorder_id)
        )
        current_status = status_row.scalar_one_or_none()
        if current_status not in {'pending_review', 'reviewing', 'stashed'}:
            raise HTTPException(status_code=409, detail="当前工单状态不允许暂存")
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
            status_result = await db.execute(
                sa_update(WorkOrderReview)
                .where(WorkOrderReview.id == workorder_id)
                .where(WorkOrderReview.review_status.in_(['pending_review', 'reviewing', 'stashed']))
                .values(review_status='stashed')
            )
            if status_result.rowcount == 0:
                raise HTTPException(status_code=409, detail="当前工单状态不允许暂存")

    if request.mode == "manual":
        # Release lock so others can pick up the ticket
        svc = ReviewService(db)
        await lock_service.release(
            workorder_id, current_user.user_id, request.lock_fencing_token,
        )

    return {"status": "ok"}


@router.get("/{workorder_id}/stash", response_model=StashData)
async def get_stash(
    workorder_id: str,
    current_user: CurrentUser = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """获取暂存的审核进度。无暂存时返回空数据，避免将正常初始状态报为 404。"""
    result = await db.execute(
        select(WorkOrderStash).where(WorkOrderStash.workorder_id == workorder_id)
    )
    stash = result.scalar_one_or_none()
    if stash is None:
        return StashData()

    return StashData(
        field_states=stash.field_states,
        notes=stash.notes or "",
        updated_at=stash.updated_at.isoformat() if stash.updated_at else None,
    )


@router.delete("/{workorder_id}/stash", response_model=StashResponse)
async def delete_stash(
    workorder_id: str,
    fencing_token: int = Header(alias="X-Lock-Fencing-Token"),
    current_user: CurrentUser = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """删除暂存的审核进度（用户丢弃修改时调用）。"""
    lock_service = get_lock_service()
    owner = await lock_service.get_owner(workorder_id)
    if (owner is None or owner["operator_id"] != current_user.user_id
            or owner.get("fencing_token") != fencing_token):
        raise HTTPException(status_code=423, detail="请先获取编辑锁")

    async with db.begin():
        svc = ReviewService(db)
        await svc.delete_stash(workorder_id)
    return {"status": "ok"}


@router.get("/{workorder_id}/audit-logs", response_model=list[AuditLogEntry])
async def get_audit_logs(
    workorder_id: str,
    current_user: CurrentUser = Depends(require_any_role),
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


# ---- Admin endpoints for sync management ----

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


@admin_router.post("/import")
async def import_new_workorders(
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """将源表新增工单幂等导入审核队列。"""
    try:
        count = await import_workorders(db)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"imported": count}


@admin_router.get("/sync-failures")
async def list_sync_failures(
    limit: int = 50,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """列出同步失败的工单（sync_status='failed'）。"""
    result = await db.execute(
        select(WorkOrderReview)
        .where(WorkOrderReview.sync_status.in_(('failed', 'uncertain')))
        .order_by(WorkOrderReview.reviewed_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "ticket_no": r.ticket_no,
            "sync_attempts": r.sync_attempts,
            "sync_last_error": r.sync_last_error,
            "sync_status": r.sync_status,
            "sync_external_id": r.sync_external_id,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        }
        for r in rows
    ]


@admin_router.post("/sync-failures/{workorder_id}/retry")
async def retry_sync(
    workorder_id: str,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """手动重试指定工单的销售易同步。

    支持 failed / pending 状态的工单重试。已存在 sync_external_id
    的记录（幂等已完成）将被直接标记为 synced 而不重复调用 API。
    """
    result = await db.execute(
        select(WorkOrderReview).where(WorkOrderReview.id == workorder_id)
    )
    wo = result.scalar_one_or_none()
    if wo is None:
        raise HTTPException(status_code=404, detail="工单不存在")

    if wo.sync_status not in ('failed', 'pending'):
        raise HTTPException(
            status_code=400,
            detail=f"工单同步状态为 '{wo.sync_status}'，只有 'failed' 或 'pending' 状态可以重试",
        )

    # 如果已有 external_id，直接标记为 synced（幂等已完成）
    if wo.sync_external_id:
        await db.execute(
            sa_update(WorkOrderReview)
            .where(WorkOrderReview.id == workorder_id)
            .values(sync_status='synced'),
        )
        await db.commit()
        return {"status": "synced", "workorder_id": workorder_id, "note": "已有 external_id，已标记为 synced"}

    # 使用已有的幂等键或生成新的重试键
    idempotency_key = wo.sync_idempotency_key or f"retry-{workorder_id}-{uuid.uuid4().hex[:8]}"

    # 后台任务统一只认领 pending；人工重试 failed 时先显式恢复为 pending。
    if wo.sync_status == 'failed':
        await db.execute(
            sa_update(WorkOrderReview)
            .where(WorkOrderReview.id == workorder_id)
            .where(WorkOrderReview.sync_status == 'failed')
            .values(sync_status='pending', sync_last_error=None, sync_started_at=None),
        )
        await db.commit()

    # 后台重试
    background_tasks.add_task(
        background_sync_to_xiaoshouyi,
        workorder_id,
        idempotency_key,
        async_session,
    )

    return {"status": "retrying", "workorder_id": workorder_id}


class ReconcileSyncRequest(BaseModel):
    external_id: str = Field(min_length=1, max_length=64)


@admin_router.post("/sync-uncertain/{workorder_id}/reconcile")
async def reconcile_uncertain_sync(
    workorder_id: str,
    request: ReconcileSyncRequest,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """人工确认销售易已创建工单，并绑定其外部工单号。"""
    external_id = request.external_id.strip()
    if not external_id:
        raise HTTPException(status_code=422, detail="销售易外部工单号不能为空")
    result = await db.execute(
        sa_update(WorkOrderReview)
        .where(WorkOrderReview.id == workorder_id)
        .where(WorkOrderReview.sync_status == 'uncertain')
        .where(WorkOrderReview.sync_external_id.is_(None))
        .values(
            sync_status='synced',
            sync_external_id=external_id,
            sync_last_error=None,
        )
        .returning(WorkOrderReview.ticket_no)
    )
    ticket_no = result.scalar_one_or_none()
    if ticket_no is None:
        check = await db.execute(select(WorkOrderReview).where(WorkOrderReview.id == workorder_id))
        if check.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="工单不存在")
        raise HTTPException(status_code=409, detail="只有结果待核实且尚未绑定外部单号的工单可以对账")
    await db.commit()
    return {
        "status": "synced",
        "workorder_id": workorder_id,
        "ticket_no": ticket_no,
        "sync_external_id": external_id,
    }


@admin_router.post("/sync-uncertain/{workorder_id}/confirm-not-created")
async def confirm_uncertain_not_created(
    workorder_id: str,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """人工确认销售易未创建工单，将 uncertain 转为可人工重试的 failed。"""
    result = await db.execute(
        sa_update(WorkOrderReview)
        .where(WorkOrderReview.id == workorder_id)
        .where(WorkOrderReview.sync_status == 'uncertain')
        .where(WorkOrderReview.sync_external_id.is_(None))
        .values(
            sync_status='failed',
            sync_attempts=0,
            sync_last_error='管理员已核实销售易未创建，可人工重试',
            sync_started_at=None,
        )
        .returning(WorkOrderReview.ticket_no)
    )
    ticket_no = result.scalar_one_or_none()
    if ticket_no is None:
        check = await db.execute(select(WorkOrderReview).where(WorkOrderReview.id == workorder_id))
        if check.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="工单不存在")
        raise HTTPException(status_code=409, detail="只有结果待核实且未绑定外部单号的工单可以确认未创建")
    await db.commit()
    return {"status": "failed", "workorder_id": workorder_id, "ticket_no": ticket_no}
