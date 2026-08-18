import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import logging
import sys
import time
import uuid

# 确保 backend/ 在 sys.path 中，PyCharm 直接运行本文件也能找到 app 包
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.routers import lock, review, stats
from app.services.lock_service import get_lock_service
from app.services.review_service import recover_orphan_syncs
from app.core.database import async_session, dispose_engine
from app.core.config import settings
from sqlalchemy import text

# ---- Structured Logging ----
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
)
logger = logging.getLogger(__name__)


# ---- Request ID Middleware ----
class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request.state.request_id = request_id
        start = time.monotonic()
        try:
            response = await call_next(request)
            elapsed_ms = round((time.monotonic() - start) * 1000)
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "%s %s → %s (%dms) [%s]",
                request.method, request.url.path,
                response.status_code, elapsed_ms, request_id,
            )
            return response
        except Exception:
            elapsed_ms = round((time.monotonic() - start) * 1000)
            logger.error(
                "%s %s → 500 (%dms) [%s]",
                request.method, request.url.path,
                elapsed_ms, request_id,
                exc_info=True,
            )
            raise


# ---- Lifecycle (startup recovery + periodic sweeper + graceful shutdown) ----
@asynccontextmanager
async def lifespan(application: FastAPI):
    """应用生命周期：启动/周期恢复孤儿同步记录，关闭时清理连接。"""
    # 保存后台任务引用，便于异常追踪
    background_tasks: set[asyncio.Task] = set()

    def _on_task_done(task: asyncio.Task) -> None:
        background_tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("后台同步任务异常", exc_info=exc)

    def _schedule_sync(fn, wid, key, sf, *args) -> None:
        task = asyncio.create_task(fn(wid, key, sf, *args))
        background_tasks.add(task)
        task.add_done_callback(_on_task_done)

    async def _sweeper_loop() -> None:
        """周期复用恢复逻辑，兜底进程崩溃后 pending 滞留 / 后台任务丢失。

        首次 sleep 后再扫（启动时已恢复一次），interval=0 时禁用。
        """
        interval = settings.XIAOSHOUYI_SWEEP_INTERVAL_SECONDS
        if interval <= 0:
            return
        while True:
            await asyncio.sleep(interval)
            try:
                n = await recover_orphan_syncs(
                    async_session, _schedule_sync,
                    per_cycle_cap=settings.XIAOSHOUYI_SWEEP_MAX_PER_CYCLE,
                )
                if n:
                    logger.info("周期扫描恢复 %d 条同步记录", n)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("周期扫描同步记录异常")

    # 启动：恢复崩溃后遗留的 pending/syncing 记录
    count = await recover_orphan_syncs(async_session, _schedule_sync)
    if count > 0:
        logger.info("启动时恢复了 %d 条孤儿同步记录", count)

    sweeper_task = asyncio.create_task(_sweeper_loop())

    yield
    # 关闭 Redis 连接池
    try:
        lock_service = get_lock_service()
        await lock_service.close()
        logger.info("LockService Redis connection closed")
    except Exception:
        logger.warning("Failed to close LockService", exc_info=True)

    # 取消未完成的后台任务与周期扫描（优先于数据库关闭，避免任务操作已释放的连接）
    sweeper_task.cancel()
    for task in list(background_tasks):
        task.cancel()
    cancel_tasks = [sweeper_task, *background_tasks]
    if cancel_tasks:
        await asyncio.gather(*cancel_tasks, return_exceptions=True)

    # 关闭销售易客户端单例（httpx 连接池 + token 缓存）
    try:
        from app.clients.xiaoshouyi import close_xiaoshouyi_client
        await close_xiaoshouyi_client()
        logger.info("XiaoShouYi client closed")
    except Exception:
        logger.warning("Failed to close XiaoShouYi client", exc_info=True)

    # 关闭数据库连接池
    try:
        await dispose_engine()
        logger.info("Database engine disposed")
    except Exception:
        logger.warning("Failed to dispose database engine", exc_info=True)


app = FastAPI(lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5193",
        "https://shouhou-gongdan-dev.example.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID + request logging
app.add_middleware(RequestIDMiddleware)

# Routers
app.include_router(lock.router)
app.include_router(review.router)
app.include_router(review.admin_router)
app.include_router(stats.router)


# ---- Health Check ----
@app.get("/health")
async def health_check():
    """健康检查端点 — 可用于 Docker healthcheck / K8s liveness probe。"""
    return {
        "status": "ok",
        "service": "shouhou-gongdan-backend",
    }


@app.get("/ready")
async def readiness_check():
    """就绪探针：依赖与核心数据库契约均可用时才接收审核流量。"""
    checks = {"database": False, "schema": False, "redis": False}
    try:
        async with async_session() as db:
            await db.execute(text("SELECT 1"))
            schema_ok = await db.scalar(text("""
                SELECT to_regclass('public.ticket') IS NOT NULL
                   AND to_regclass('public.ticket_view') IS NOT NULL
                   AND to_regclass('public.workorder_review') IS NOT NULL
                   AND to_regclass('public.review_submission') IS NOT NULL
                   AND EXISTS (
                       SELECT 1 FROM information_schema.columns
                       WHERE table_schema='public' AND table_name='workorder_review'
                         AND column_name='ticket_id'
                   )
                   AND NOT EXISTS (
                       SELECT 1 FROM information_schema.columns
                       WHERE table_schema='public' AND table_name='workorder_review'
                         AND column_name='ticket_no'
                   )
                   AND EXISTS (
                       SELECT 1 FROM information_schema.columns
                       WHERE table_schema='public' AND table_name='ticket_view'
                         AND column_name='stationName'
                   )
            """))
        checks["database"] = True
        checks["schema"] = bool(schema_ok)
    except Exception:
        logger.warning("readiness database check failed", exc_info=True)
    try:
        checks["redis"] = bool(await get_lock_service().redis.ping())
    except Exception:
        logger.warning("readiness redis check failed", exc_info=True)
    return ({"status": "ready", "checks": checks} if all(checks.values())
            else JSONResponse(status_code=503, content={"status": "not_ready", "checks": checks}))


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8093, reload=True)
