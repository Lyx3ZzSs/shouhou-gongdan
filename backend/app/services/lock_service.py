import asyncio
import json
from datetime import datetime, timezone

import redis.asyncio as aioredis
import redis.exceptions

from app.core.config import settings

LOCK_PREFIX = "review_lock:"
FENCE_PREFIX = "review_fence:"
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
    _ACQUIRE_SCRIPT = """
    if redis.call('exists', KEYS[1]) == 0 then
        local current = tonumber(redis.call('get', KEYS[2]) or '0')
        local floor = tonumber(ARGV[3])
        if current < floor then redis.call('set', KEYS[2], floor) end
        local token = redis.call('incr', KEYS[2])
        local value = cjson.decode(ARGV[1])
        value['fencing_token'] = token
        redis.call('set', KEYS[1], cjson.encode(value), 'ex', ARGV[2])
        return {1, token}
    end
    return {0, 0}
    """
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

    _REFRESH_SCRIPT = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
        redis.call('set', KEYS[1], ARGV[2], 'ex', ARGV[3])
        return 1
    else
        return 0
    end
    """

    def __init__(self):
        self._redis = None
        self._loop_id = None
        self._release_sha: str | None = None
        self._heartbeat_sha: str | None = None
        self._refresh_sha: str | None = None
        self._acquire_sha: str | None = None

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
            self._refresh_sha = None
            self._acquire_sha = None
        return self._redis

    @staticmethod
    def _encode_value(
        operator_id: str, operator_name: str, locked_at: str,
        fencing_token: int | None = None,
    ) -> str:
        """将锁值编码为 JSON，避免冒号等特殊字符导致解析错误。"""
        value = {
            "operator_id": operator_id,
            "operator_name": operator_name,
            "locked_at": locked_at,
        }
        if fencing_token is not None:
            value["fencing_token"] = fencing_token
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _decode_value(raw: bytes) -> dict:
        """从 JSON 解码锁值，返回 {operator_id, operator_name, locked_at}。
        兼容旧版冒号分隔格式，避免部署时 JSONDecodeError。"""
        text = raw.decode()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 兼容旧版格式：operator_id:operator_name:locked_at（locked_at 含冒号）
            parts = text.split(":", maxsplit=2)
            if len(parts) == 3:
                return {
                    "operator_id": parts[0],
                    "operator_name": parts[1],
                    "locked_at": parts[2],
                }
            raise

    async def _eval_script(
        self, key: str, value: str, ttl: int | None,
        sha_attr: str, script: str,
    ) -> int:
        """执行原子 Lua 脚本，自动处理 NoScriptError（Redis 重启后 SHA 失效）。"""
        sha = getattr(self, sha_attr)
        if sha is None:
            sha = await self.redis.script_load(script)
            setattr(self, sha_attr, sha)

        args = [key, value] if ttl is None else [key, value, ttl]
        try:
            return await self.redis.evalsha(sha, 1, *args)
        except redis.exceptions.NoScriptError:
            # Redis 重启或 SCRIPT FLUSH，重新加载脚本
            sha = await self.redis.script_load(script)
            setattr(self, sha_attr, sha)
            return await self.redis.evalsha(sha, 1, *args)

    async def _eval_release(self, key: str, value: str) -> int:
        """执行原子 release Lua 脚本，返回删除的 key 数量。"""
        return await self._eval_script(
            key, value, None,
            "_release_sha", self._RELEASE_SCRIPT,
        )

    async def _eval_heartbeat(self, key: str, value: str, ttl: int) -> int:
        """执行原子 heartbeat Lua 脚本，返回 1 表示成功续期。"""
        return await self._eval_script(
            key, value, ttl,
            "_heartbeat_sha", self._HEARTBEAT_SCRIPT,
        )

    async def _eval_refresh(self, key: str, old_value: str, new_value: str, ttl: int) -> int:
        """原子化刷新锁值：仅在当前值匹配 old_value 时更新为 new_value。
        消除幂等重获取的 TOCTOU 窗口。返回 1 表示成功。"""
        sha = self._refresh_sha
        if sha is None:
            sha = await self.redis.script_load(self._REFRESH_SCRIPT)
            self._refresh_sha = sha
        try:
            return await self.redis.evalsha(sha, 1, key, old_value, new_value, ttl)
        except redis.exceptions.NoScriptError:
            sha = await self.redis.script_load(self._REFRESH_SCRIPT)
            self._refresh_sha = sha
            return await self.redis.evalsha(sha, 1, key, old_value, new_value, ttl)

    async def acquire(
        self, workorder_id: str, operator_id: str, operator_name: str,
        token_floor: int = 0,
    ) -> dict:
        """获取锁。返回 {locked, owner, locked_minutes?}"""
        key = f"{LOCK_PREFIX}{workorder_id}"
        now = datetime.now(timezone.utc).isoformat()
        value = self._encode_value(operator_id, operator_name, now)

        fence_key = f"{FENCE_PREFIX}{workorder_id}"
        client = self.redis
        if self._acquire_sha is None:
            self._acquire_sha = await client.script_load(self._ACQUIRE_SCRIPT)
        try:
            ok, token = await client.evalsha(
                self._acquire_sha, 2, key, fence_key, value, LOCK_TTL, token_floor,
            )
        except redis.exceptions.NoScriptError:
            self._acquire_sha = await client.script_load(self._ACQUIRE_SCRIPT)
            ok, token = await client.evalsha(
                self._acquire_sha, 2, key, fence_key, value, LOCK_TTL, token_floor,
            )
        if ok:
            return {"locked": True, "owner": operator_name, "is_new": True,
                    "fencing_token": int(token)}

        # 锁已被他人持有，读取持有者信息
        existing = await self.redis.get(key)
        if existing:
            data = self._decode_value(existing)
            owner_id = data["operator_id"]
            owner_name = data["operator_name"]
            locked_at = data["locked_at"]
            if owner_id == operator_id:
                # 幂等：同一持有者重复获取，原子化刷新值 + TTL（消除 TOCTOU 窗口）
                now = datetime.now(timezone.utc).isoformat()
                old_value = existing.decode()
                new_value = self._encode_value(
                    operator_id, owner_name, now, data.get("fencing_token"),
                )
                result = await self._eval_refresh(key, old_value, new_value, LOCK_TTL)
                if result:
                    return {"locked": True, "owner": owner_name, "is_new": False,
                            "fencing_token": data.get("fencing_token")}
                # 原子刷新失败 — 锁已被他人获取或已过期
                return {"locked": False, "owner": "unknown", "is_new": False}
            else:
                # 计算实际锁定分钟数
                locked_at_dt = datetime.fromisoformat(locked_at)
                if locked_at_dt.tzinfo is None:
                    locked_at_dt = locked_at_dt.replace(tzinfo=timezone.utc)
                elapsed = (datetime.now(timezone.utc) - locked_at_dt).total_seconds()
                locked_minutes = max(1, int(elapsed / 60) + 1)
                return {"locked": False, "owner": owner_name, "locked_minutes": locked_minutes, "is_new": False}

        # 锁在获取和读取之间过期，重试并生成新的单调 token。
        return await self.acquire(workorder_id, operator_id, operator_name, token_floor)

    async def release(
        self, workorder_id: str, operator_id: str, fencing_token: int | None = None,
    ) -> None:
        """释放锁（原子）。仅持有者可释放，否则抛出 PermissionError"""
        key = f"{LOCK_PREFIX}{workorder_id}"
        # 先读当前值构造完整 value（Lua 脚本需要完整匹配）
        existing = await self.redis.get(key)
        if not existing:
            return  # 锁已过期，无需操作
        value = existing.decode()
        data = self._decode_value(existing)
        if data["operator_id"] != operator_id:
            raise PermissionError("仅锁持有者可释放")
        if fencing_token is not None and data.get("fencing_token") != fencing_token:
            raise PermissionError("编辑锁租约已失效")

        result = await self._eval_release(key, value)
        if result == 0:
            raise PermissionError("锁已被他人获取或已过期")

    async def heartbeat(self, workorder_id: str, operator_id: str, fencing_token: int) -> None:
        """心跳续期（原子）。仅持有者可续期，否则抛出 LockLostError"""
        key = f"{LOCK_PREFIX}{workorder_id}"
        existing = await self.redis.get(key)
        if not existing:
            raise LockLostError("编辑锁已过期，请刷新页面")
        value = existing.decode()
        data = self._decode_value(existing)
        if data["operator_id"] != operator_id:
            raise LockLostError("编辑锁已被他人获取，请刷新页面")
        if data.get("fencing_token") != fencing_token:
            raise LockLostError("编辑锁租约已失效，请刷新页面")

        result = await self._eval_heartbeat(key, value, LOCK_TTL)
        if result == 0:
            raise LockLostError("编辑锁续期失败，请刷新页面")

    async def get_owner(self, workorder_id: str) -> dict | None:
        """Return the current lock owner, or None if not locked."""
        key = f"{LOCK_PREFIX}{workorder_id}"
        existing = await self.redis.get(key)
        if not existing:
            return None
        data = self._decode_value(existing)
        return {
            "operator_id": data["operator_id"],
            "operator_name": data["operator_name"],
            "locked_at": data["locked_at"],
            "fencing_token": data.get("fencing_token"),
        }

    async def close(self) -> None:
        """关闭 Redis 连接池（用于应用优雅关闭）。"""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
            self._loop_id = None


class LockLostError(Exception):
    pass
