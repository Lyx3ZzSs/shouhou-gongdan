import asyncio
from collections.abc import Callable
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
from starlette.middleware.base import BaseHTTPMiddleware

from app.routers import lock, review, stats
from app.services.lock_service import get_lock_service
from app.services.review_service import recover_orphan_syncs
from app.core.database import async_session, dispose_engine

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


# ---- Background Task Helpers ----


def _track_task(
    task_set: set[asyncio.Task],
    task: asyncio.Task,
    on_done: Callable[[asyncio.Task], None],
) -> None:
    """保存 Task 引用并注册完成回调，防止异步异常丢失。"""
    task_set.add(task)
    task.add_done_callback(on_done)


# ---- Lifecycle (startup recovery + graceful shutdown) ----
@asynccontextmanager
async def lifespan(application: FastAPI):
    """应用生命周期：启动时恢复孤儿同步记录，关闭时清理连接。"""
    # 保存后台任务引用，便于异常追踪
    background_tasks: set[asyncio.Task] = set()

    def _on_task_done(task: asyncio.Task) -> None:
        background_tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("后台同步任务异常", exc_info=exc)

    # 启动：恢复崩溃后遗留的 pending/syncing 记录
    count = await recover_orphan_syncs(
        async_session,
        lambda fn, wid, key, sf: _track_task(
            background_tasks,
            asyncio.create_task(fn(wid, key, sf)),
            _on_task_done,
        ),
    )
    if count > 0:
        logger.info("启动时恢复了 %d 条孤儿同步记录", count)

    yield
    # 关闭 Redis 连接池
    try:
        lock_service = get_lock_service()
        await lock_service.close()
        logger.info("LockService Redis connection closed")
    except Exception:
        logger.warning("Failed to close LockService", exc_info=True)

    # 取消未完成的后台任务（优先于数据库关闭，避免任务操作已释放的连接）
    for task in list(background_tasks):
        task.cancel()
    if background_tasks:
        await asyncio.gather(*background_tasks, return_exceptions=True)

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


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8093, reload=True)
