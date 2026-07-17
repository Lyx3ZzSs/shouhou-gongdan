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
        now = datetime.datetime.now(datetime.UTC).isoformat()
        value = f"{operator_id}:{operator_name}:{now}"

        # 原子尝试获取锁：SET NX 只在 key 不存在时写入
        ok = await self.redis.set(key, value, nx=True, ex=LOCK_TTL)
        if ok:
            return {"locked": True, "owner": operator_name}

        # 锁已被他人持有，读取持有者信息
        existing = await self.redis.get(key)
        if existing:
            owner_id, owner_name, locked_at = existing.decode().split(":", maxsplit=2)
            if owner_id == operator_id:
                # 幂等：同一持有者重复获取，刷新 TTL
                await self.redis.expire(key, LOCK_TTL)
                return {"locked": True, "owner": owner_name}
            else:
                # 计算实际锁定分钟数
                locked_at_dt = datetime.datetime.fromisoformat(locked_at)
                now = datetime.datetime.now(datetime.UTC)
                if locked_at_dt.tzinfo is None:
                    locked_at_dt = locked_at_dt.replace(tzinfo=datetime.UTC)
                elapsed = (now - locked_at_dt).total_seconds()
                locked_minutes = max(1, int(elapsed / 60) + 1)
                return {"locked": False, "owner": owner_name, "locked_minutes": locked_minutes}

        # 锁在 SET NX 和 GET 之间过期（极端情况），视为可获取
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
