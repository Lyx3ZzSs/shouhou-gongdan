from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user, CurrentUser
from app.services.lock_service import LockService, LockLostError

router = APIRouter(prefix="/api/workorders", tags=["lock"])


@router.post("/{workorder_id}/lock")
async def acquire_lock(
    workorder_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    service = LockService()
    return await service.acquire(workorder_id, current_user.user_id, current_user.name)


@router.delete("/{workorder_id}/lock")
async def release_lock(
    workorder_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    service = LockService()
    try:
        await service.release(workorder_id, current_user.user_id)
        return {"status": "released"}
    except PermissionError:
        raise HTTPException(status_code=403, detail="仅锁持有者可释放")


@router.put("/{workorder_id}/lock")
async def heartbeat_lock(
    workorder_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    service = LockService()
    try:
        await service.heartbeat(workorder_id, current_user.user_id)
        return {"status": "ok"}
    except LockLostError as e:
        raise HTTPException(status_code=423, detail=str(e))
