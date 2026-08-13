import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
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
    status_result = await db.execute(
        text("SELECT review_status, lock_fencing_token FROM workorder_review WHERE id = :id"),
        {"id": workorder_id},
    )
    row = status_result.mappings().first()
    status = row["review_status"] if row else None
    if status not in {'pending_review', 'reviewing', 'stashed'}:
        raise HTTPException(status_code=409, detail="当前工单状态不允许编辑")

    service = get_lock_service()
    result = await service.acquire(
        workorder_id, current_user.user_id, current_user.display_name,
        token_floor=row["lock_fencing_token"],
    )

    # 锁首次获取成功时，记录审核开始时间
    if result.get("is_new") and result.get("locked"):
        try:
            update_result = await db.execute(text("""
                UPDATE workorder_review
                SET review_started_at = COALESCE(review_started_at, :now),
                    lock_fencing_token = :token
                WHERE id = :id
                  AND review_status IN ('pending_review', 'reviewing', 'stashed')
                  AND lock_fencing_token < :token
            """), {"now": datetime.now(timezone.utc), "id": workorder_id,
                    "token": result["fencing_token"]})
            if update_result.rowcount == 0:
                await db.rollback()
                await service.release(workorder_id, current_user.user_id, result["fencing_token"])
                raise HTTPException(status_code=409, detail="当前工单状态不允许编辑")
            await db.commit()
        except HTTPException:
            raise
        except Exception:
            await db.rollback()
            await service.release(workorder_id, current_user.user_id, result["fencing_token"])
            logger.exception("记录审核 fencing token 失败 workorder=%s", workorder_id)
            raise HTTPException(status_code=503, detail="获取编辑锁失败，请重试")

    return result


@router.delete("/{workorder_id}/lock", response_model=LockStatus)
async def release_lock(
    workorder_id: str,
    fencing_token: int = Header(alias="X-Lock-Fencing-Token"),
    current_user: CurrentUser = Depends(get_current_user),
):
    service = get_lock_service()
    try:
        await service.release(workorder_id, current_user.user_id, fencing_token)
        return {"status": "released"}
    except PermissionError:
        raise HTTPException(status_code=403, detail="仅锁持有者可释放")


@router.put("/{workorder_id}/lock", response_model=LockStatus)
async def heartbeat_lock(
    workorder_id: str,
    fencing_token: int = Header(alias="X-Lock-Fencing-Token"),
    current_user: CurrentUser = Depends(get_current_user),
):
    service = get_lock_service()
    try:
        await service.heartbeat(workorder_id, current_user.user_id, fencing_token)
        return {"status": "ok"}
    except LockLostError as e:
        raise HTTPException(status_code=423, detail=str(e))
