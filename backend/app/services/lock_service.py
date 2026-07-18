import asyncio
import datetime

import redis.asyncio as aioredis

from app.core.config import settings

LOCK_PREFIX = "review_lock:"
LOCK_TTL = 300  # 5 分钟


_lock_service = None


def get_lock_service():
    """返回 LockService 的模块级单例，避免每次请求创建新的 Redis 连接池。
    Redis 客户端通过 @property 懒初始化，并在事件循环切换时自动重建。"""
    global _lock_service
    if _lock_service is None:
        _lock_service = LockService()
    return _lock_service


class LockService:
    # Lua 脚本：原子化 release 和 heartbeat，消除 TOCTOU 竞态
    _RELEASE_SCRIPT = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
        return redis.call('del', KEYS[1])
    else
        return 0
    end
    """

    _HEARTBEAT_SCRIPT = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
        return redis.call('expire', KEYS[1], ARGV[2])
    else
        return 0
    end
    """

    def __init__(self):
        self._redis = None
        self._loop_id = None
        self._release_sha: str | None = None
        self._heartbeat_sha: str | None = None

    @property
    def redis(self):
        """懒初始化 Redis 连接，事件循环切换时自动重建。"""
        try:
            current_loop_id = id(asyncio.get_running_loop())
        except RuntimeError:
            current_loop_id = None
        if self._redis is None or self._loop_id != current_loop_id:
            self._redis = aioredis.from_url(settings.REDIS_URL)
            self._loop_id = current_loop_id
            self._release_sha = None
            self._heartbeat_sha = None
        return self._redis

    async def _eval_release(self, key: str, value: str) -> int:
        """执行原子 release Lua 脚本，返回删除的 key 数量。"""
        if self._release_sha is None:
            self._release_sha = await self.redis.script_load(self._RELEASE_SCRIPT)
        return await self.redis.evalsha(self._release_sha, 1, key, value)

    async def _eval_heartbeat(self, key: str, value: str, ttl: int) -> int:
        """执行原子 heartbeat Lua 脚本，返回 1 表示成功续期。"""
        if self._heartbeat_sha is None:
            self._heartbeat_sha = await self.redis.script_load(self._HEARTBEAT_SCRIPT)
        return await self.redis.evalsha(self._heartbeat_sha, 1, key, value, ttl)

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
                if locked_at_dt.tzinfo is None:
                    locked_at_dt = locked_at_dt.replace(tzinfo=datetime.UTC)
                elapsed = (datetime.datetime.now(datetime.UTC) - locked_at_dt).total_seconds()
                locked_minutes = max(1, int(elapsed / 60) + 1)
                return {"locked": False, "owner": owner_name, "locked_minutes": locked_minutes}

        # 锁在 SET NX 和 GET 之间过期（极端情况），重试一次 SET NX
        ok = await self.redis.set(key, value, nx=True, ex=LOCK_TTL)
        if ok:
            return {"locked": True, "owner": operator_name}
        # 仍然失败，返回已锁定
        return {"locked": False, "owner": "unknown"}

    async def release(self, workorder_id: str, operator_id: str) -> None:
        """释放锁（原子）。仅持有者可释放，否则抛出 PermissionError"""
        key = f"{LOCK_PREFIX}{workorder_id}"
        value_prefix = f"{operator_id}:"
        # 先读当前值构造完整 value（Lua 脚本需要完整匹配）
        existing = await self.redis.get(key)
        if not existing:
            return  # 锁已过期，无需操作
        value = existing.decode()
        if not value.startswith(value_prefix):
            raise PermissionError("仅锁持有者可释放")

        result = await self._eval_release(key, value)
        if result == 0:
            raise PermissionError("锁已被他人获取或已过期")

    async def heartbeat(self, workorder_id: str, operator_id: str) -> None:
        """心跳续期（原子）。仅持有者可续期，否则抛出 LockLostError"""
        key = f"{LOCK_PREFIX}{workorder_id}"
        value_prefix = f"{operator_id}:"
        existing = await self.redis.get(key)
        if not existing:
            raise LockLostError("编辑锁已过期，请刷新页面")
        value = existing.decode()
        if not value.startswith(value_prefix):
            raise LockLostError("编辑锁已被他人获取，请刷新页面")

        result = await self._eval_heartbeat(key, value, LOCK_TTL)
        if result == 0:
            raise LockLostError("编辑锁续期失败，请刷新页面")

    async def get_owner(self, workorder_id: str) -> dict | None:
        """Return the current lock owner, or None if not locked."""
        key = f"{LOCK_PREFIX}{workorder_id}"
        existing = await self.redis.get(key)
        if not existing:
            return None
        owner_id, owner_name, locked_at = existing.decode().split(":", maxsplit=2)
        return {"operator_id": owner_id, "operator_name": owner_name, "locked_at": locked_at}


class LockLostError(Exception):
    pass
