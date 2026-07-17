import datetime

import redis.asyncio as aioredis

from app.core.config import settings

LOCK_PREFIX = "review_lock:"
LOCK_TTL = 300  # 5 分钟


class LockService:
    def __init__(self):
        self.redis = aioredis.from_url(settings.REDIS_URL)

    async def acquire(self, workorder_id: str, operator_id: str, operator_name: str) -> dict:
        """获取锁。返回 {locked, owner, locked_minutes?}"""
        key = f"{LOCK_PREFIX}{workorder_id}"
        existing = await self.redis.get(key)
        if existing:
            owner_id, owner_name, locked_at = existing.decode().split(":", maxsplit=2)
            if owner_id == operator_id:
                await self.redis.expire(key, LOCK_TTL)  # 幂等：刷新 TTL
                return {"locked": True, "owner": owner_name}
            else:
                return {"locked": False, "owner": owner_name, "locked_minutes": 3}
        else:
            now = datetime.datetime.now(datetime.UTC).isoformat()
            value = f"{operator_id}:{operator_name}:{now}"
            await self.redis.set(key, value, ex=LOCK_TTL)
            return {"locked": True, "owner": operator_name}

    async def release(self, workorder_id: str, operator_id: str) -> None:
        """释放锁。仅持有者可释放，否则抛出 PermissionError"""
        key = f"{LOCK_PREFIX}{workorder_id}"
        existing = await self.redis.get(key)
        if not existing:
            return  # 锁已过期，无需操作
        owner_id, _, _ = existing.decode().split(":", maxsplit=2)
        if owner_id != operator_id:
            raise PermissionError("仅锁持有者可释放")

        await self.redis.delete(key)

    async def heartbeat(self, workorder_id: str, operator_id: str) -> None:
        """心跳续期。仅持有者可续期，否则抛出 LockLostError"""
        key = f"{LOCK_PREFIX}{workorder_id}"
        existing = await self.redis.get(key)
        if not existing:
            raise LockLostError("编辑锁已过期，请刷新页面")
        owner_id, _, _ = existing.decode().split(":", maxsplit=2)
        if owner_id != operator_id:
            raise LockLostError("编辑锁已被他人获取，请刷新页面")

        await self.redis.expire(key, LOCK_TTL)


class LockLostError(Exception):
    pass
