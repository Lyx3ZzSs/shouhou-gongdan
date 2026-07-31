import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, CurrentUser
from app.core.database import get_db
from app.services.lock_service import get_lock_service, LockLostError
from app.schemas.review import LockStatus

router = APIRouter(prefix="/api/workorders", tags=["lock"])
logger = logging.getLogger(__name__)


@router.post("/{workorder_id}/lock", response_model=LockStatus)
async def acquire_lock(
    workorder_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = get_lock_service()
    result = await service.acquire(workorder_id, current_user.user_id, current_user.display_name)

    # 锁首次获取成功时，记录审核开始时间
    if result.get("is_new") and result.get("locked"):
        try:
            await db.execute(
                text("UPDATE workorder SET review_started_at = :now WHERE id = :id AND review_started_at IS NULL"),
                {"now": datetime.now(timezone.utc), "id": workorder_id},
            )
            await db.commit()
        except Exception:
            await db.rollback()
            logger.warning("记录审核开始时间失败 workorder=%s", workorder_id, exc_info=True)

    return result


@router.delete("/{workorder_id}/lock", response_model=LockStatus)
async def release_lock(
    workorder_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    service = get_lock_service()
    try:
        await service.release(workorder_id, current_user.user_id)
        return {"status": "released"}
    except PermissionError:
        raise HTTPException(status_code=403, detail="仅锁持有者可释放")


@router.put("/{workorder_id}/lock", response_model=LockStatus)
async def heartbeat_lock(
    workorder_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    service = get_lock_service()
    try:
        await service.heartbeat(workorder_id, current_user.user_id)
        return {"status": "ok"}
    except LockLostError as e:
        raise HTTPException(status_code=423, detail=str(e))
