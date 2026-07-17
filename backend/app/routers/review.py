from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.auth.dependencies import get_current_user, CurrentUser
from app.schemas.review import ReviewRequest, ReviewResponse, AuditLogEntry, FieldChange
from app.services.review_service import ReviewService
from app.core.database import get_db
from app.models.audit_log import WorkOrderAuditLog

router = APIRouter(prefix="/api/workorders", tags=["review"])


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


@router.get("/{workorder_id}/audit-logs")
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
            "ai_confidence": float(row.ai_confidence) if row.ai_confidence else None,
        })

    return list(sessions.values())
