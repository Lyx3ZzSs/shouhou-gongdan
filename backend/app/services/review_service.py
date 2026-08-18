import asyncio
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import text, update, delete as sa_delete, or_, select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.schemas.review import ReviewRequest, ConfirmRequest, ALLOWED_FIELDS
from app.models.workorder import WorkOrderReview
from app.models.ticket import TicketView
from app.models.workorder_stash import WorkOrderStash
from app.models.review_submission import ReviewSubmission
from app.services.audit_service import AuditService
from app.services.bad_case_service import BadCaseService
from app.services.lock_service import get_lock_service
from app.core.config import settings
from app.services.review_validation import validate_workorder
from app.clients.xiaoshouyi import (
    get_xiaoshouyi_client,
    XiaoShouYiError,
    XiaoShouYiUncertainError,
)

logger = logging.getLogger(__name__)

# 并发控制：限制同时进行的销售易同步数量，防止浪涌
_sync_semaphore: asyncio.Semaphore | None = None


def _get_sync_semaphore() -> asyncio.Semaphore:
    global _sync_semaphore
    if _sync_semaphore is None:
        _sync_semaphore = asyncio.Semaphore(settings.XIAOSHOUYI_SYNC_MAX_CONCURRENCY)
    return _sync_semaphore


@dataclass
class ConfirmResult:
    """confirm() 返回结构：分离响应字段与后台同步调度信息。"""
    response: dict  # 可直接解包传入 ConfirmResponse(**response)
    sync_idempotency_key: str | None = None  # None = 无需后台同步


async def _get_ticket_dict(db: AsyncSession, ticket_id: int) -> dict | None:
    """从 ticket_view 视图获取工单业务数据。"""
    result = await db.execute(
        select(TicketView).where(TicketView.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()
    if ticket is None:
        return None
    return ticket.to_dict()


async def background_sync_to_xiaoshouyi(
    workorder_id: str,
    sync_idempotency_key: str,
    session_factory: async_sessionmaker,
    already_claimed: bool = False,
) -> str:
    """后台同步至销售易：merge ticket_view + field_overrides → API。"""
    max_retries = settings.XIAOSHOUYI_SYNC_MAX_RETRIES
    timeout = settings.XIAOSHOUYI_SYNC_TIMEOUT_SECONDS
    if max_retries < 1:
        logger.warning("销售易同步已禁用（XIAOSHOUYI_SYNC_MAX_RETRIES=%d），workorder=%s", max_retries, workorder_id)
        return 'pending'

    last_error = None
    claimed = already_claimed
    for attempt in range(1, max_retries + 1):
        try:
            # ---- 原子认领 ----
            # 正常提交/人工重试由任务认领 pending；恢复扫描器已原子认领后通过
            # already_claimed 交接，避免扫描器先置 syncing、任务又拒绝 syncing。
            if not claimed:
                async with session_factory() as db:
                    claim_result = await db.execute(
                        text("""
                            UPDATE workorder_review
                            SET sync_status = 'syncing',
                                sync_attempts = :attempt,
                                sync_idempotency_key = :key,
                                sync_started_at = NOW(),
                                sync_last_error = NULL
                            WHERE id = :id
                              AND sync_external_id IS NULL
                              AND sync_status = 'pending'
                        """),
                        {"id": workorder_id, "attempt": attempt, "key": sync_idempotency_key},
                    )
                    if claim_result.rowcount == 0:
                        check = await db.execute(
                            text("SELECT sync_status, sync_external_id FROM workorder_review WHERE id = :id"),
                            {"id": workorder_id},
                        )
                        ext_row = check.mappings().first()
                        if ext_row and ext_row.get("sync_external_id"):
                            return 'synced'
                        logger.info("同步任务未认领 workorder=%s status=%s", workorder_id,
                                    ext_row.get("sync_status") if ext_row else "missing")
                        return ext_row.get("sync_status", "failed") if ext_row else 'failed'
                    await db.commit()
                claimed = True

            # ---- 读取审核记录 + ticket_view 业务数据 ----
            async with session_factory() as db:
                result = await db.execute(
                    text("SELECT * FROM workorder_review WHERE id = :id"),
                    {"id": workorder_id},
                )
                row = result.mappings().first()
                if row is None:
                    # 已认领为 syncing 后记录消失，必须落库失败态，否则永久卡 syncing
                    msg = f"审核记录 {workorder_id} 不存在"
                    logger.error("销售易同步失败: %s", msg)
                    await db.execute(
                        update(WorkOrderReview)
                        .where(WorkOrderReview.id == workorder_id)
                        .values(sync_status='failed', sync_attempts=attempt, sync_last_error=msg),
                    )
                    await db.commit()
                    return 'failed'

                ticket_id = row.get("ticket_id")
                overrides = row.get("field_overrides") or {}

                # 获取 ticket_view 业务数据
                ticket_dict = await _get_ticket_dict(db, ticket_id)
                if ticket_dict is None:
                    msg = f"ticket.id={ticket_id} 在 ticket_view 中不存在"
                    logger.error("销售易同步失败: %s", msg)
                    await db.execute(
                        update(WorkOrderReview)
                        .where(WorkOrderReview.id == workorder_id)
                        .values(sync_status='failed', sync_attempts=attempt, sync_last_error=msg),
                    )
                    await db.commit()
                    return 'failed'

                # merge: ticket_view 原始值 + field_overrides 覆盖
                from app.clients.xiaoshouyi import map_db_to_xiaoshouyi
                merged = {**ticket_dict, **overrides}
                req = map_db_to_xiaoshouyi(merged)

            # ---- 调用销售易 API（带并发控制）----
            # 客户端为进程级单例（共享连接池 + token 缓存），shutdown 时统一关闭
            client = get_xiaoshouyi_client()
            sem = _get_sync_semaphore()
            async def _call_with_limit():
                async with sem:
                    return await client.create_work_order(req)

            # 总超时同时覆盖并发槽等待与 HTTP 调用；httpx 内部另有分阶段超时。
            sync_result = await asyncio.wait_for(_call_with_limit(), timeout=timeout)

            # ---- 写入同步结果 ----
            async with session_factory() as db:
                if sync_result.external_id:
                    await db.execute(
                        update(WorkOrderReview)
                        .where(WorkOrderReview.id == workorder_id)
                        .values(
                            sync_status='synced',
                            sync_attempts=attempt,
                            sync_external_id=sync_result.external_id,
                        ),
                    )
                    await db.commit()
                    logger.info("销售易同步成功 workorder=%s external_id=%s attempt=%d",
                                workorder_id, sync_result.external_id, attempt)
                    return 'synced'
                else:
                    msg = "销售易返回成功但缺少外部工单号，需要人工核实"
                    await db.execute(
                        update(WorkOrderReview)
                        .where(WorkOrderReview.id == workorder_id)
                        .values(sync_status='uncertain', sync_attempts=attempt, sync_last_error=msg),
                    )
                    await db.commit()
                    logger.warning("%s workorder=%s", msg, workorder_id)
                    return 'uncertain'
        except asyncio.CancelledError:
            logger.info("销售易同步被取消 workorder=%s attempt=%d", workorder_id, attempt)
            try:
                async with session_factory() as db:
                    await db.execute(
                        update(WorkOrderReview)
                        .where(WorkOrderReview.id == workorder_id)
                        .where(WorkOrderReview.sync_status == 'syncing')
                        .values(sync_status='uncertain', sync_attempts=attempt,
                                sync_last_error='同步任务被中断，销售易结果需要人工核实'),
                    )
                    await db.commit()
            except Exception:
                logger.warning("销售易同步取消后状态重置失败 workorder=%s", workorder_id, exc_info=True)
            raise
        except XiaoShouYiUncertainError as e:
            last_error = str(e)
            logger.error("销售易同步结果不确定（禁止自动重试） workorder=%s: %s",
                         workorder_id, last_error)
            async with session_factory() as db:
                await db.execute(
                    update(WorkOrderReview)
                    .where(WorkOrderReview.id == workorder_id)
                    .values(sync_status='uncertain', sync_attempts=attempt,
                            sync_last_error=last_error),
                )
                await db.commit()
            return 'uncertain'
        except XiaoShouYiError as e:
            last_error = str(e)
            if e.retryable:
                logger.warning("销售易同步可重试错误 workorder=%s attempt=%d/%d: %s",
                               workorder_id, attempt, max_retries, last_error)
            else:
                logger.error("销售易同步不可重试错误 workorder=%s attempt=%d/%d: %s",
                             workorder_id, attempt, max_retries, last_error)
                try:
                    async with session_factory() as db:
                        await db.execute(
                            update(WorkOrderReview)
                            .where(WorkOrderReview.id == workorder_id)
                            .values(
                                sync_status='failed', sync_attempts=attempt,
                                sync_last_error=last_error,
                            ),
                        )
                        await db.commit()
                except Exception:
                    logger.exception("销售易同步失败状态写入异常 workorder=%s", workorder_id)
                return 'failed'
        except asyncio.TimeoutError as e:
            # 实证结论：销售易 idempotencyKey__c 不去重（同 key 同 body 也新建工单）。
            # 超时 = 请求可能已到达销售易并成功建单、仅响应丢失，盲目重试会重复建单，
            # 因此不再自动重试，直接标记 failed（sweeper 也不认领 failed）并提示人工核实。
            last_error = "销售易同步超时，工单可能已创建，请人工核实后处理"
            logger.error("销售易同步超时（不自动重试，防重复建单） workorder=%s attempt=%d: %s",
                         workorder_id, attempt, last_error)
            try:
                async with session_factory() as db:
                    await db.execute(
                        update(WorkOrderReview)
                        .where(WorkOrderReview.id == workorder_id)
                        .values(sync_status='uncertain', sync_attempts=attempt, sync_last_error=last_error),
                    )
                    await db.commit()
            except Exception:
                logger.exception("销售易同步超时状态写入异常 workorder=%s", workorder_id)
            return 'uncertain'
        except NotImplementedError as e:
            last_error = str(e)
            logger.warning("销售易同步未实现 workorder=%s attempt=%d/%d: %s",
                           workorder_id, attempt, max_retries, last_error)
        except Exception as e:
            last_error = f"未分类同步异常，结果需要人工核实: {e}"
            logger.exception("销售易同步未分类异常 workorder=%s", workorder_id)
            async with session_factory() as db:
                await db.execute(
                    update(WorkOrderReview)
                    .where(WorkOrderReview.id == workorder_id)
                    .values(sync_status='uncertain', sync_attempts=attempt,
                            sync_last_error=last_error),
                )
                await db.commit()
            return 'uncertain'

        if attempt >= max_retries:
            try:
                async with session_factory() as db:
                    await db.execute(
                        update(WorkOrderReview)
                        .where(WorkOrderReview.id == workorder_id)
                        .values(sync_status='failed', sync_attempts=attempt, sync_last_error=last_error),
                    )
                    await db.commit()
                logger.error("销售易同步最终失败 workorder=%s after %d attempts: %s",
                             workorder_id, max_retries, last_error)
            except Exception:
                logger.exception("销售易同步失败状态写入异常 workorder=%s", workorder_id)
            return 'failed'

        backoff = 2 ** attempt
        logger.info("销售易同步重试 workorder=%s 等待 %ds 后进行第 %d 次重试",
                    workorder_id, backoff, attempt + 1)
        try:
            await asyncio.sleep(backoff)
        except asyncio.CancelledError:
            logger.info("销售易同步在退避等待期间被取消 workorder=%s attempt=%d", workorder_id, attempt)
            try:
                async with session_factory() as db:
                    await db.execute(
                        update(WorkOrderReview)
                        .where(WorkOrderReview.id == workorder_id)
                        .values(sync_status='pending', sync_attempts=0, sync_last_error=None),
                    )
                    await db.commit()
            except Exception:
                logger.warning("销售易同步取消后状态重置失败 workorder=%s", workorder_id, exc_info=True)
            raise


async def recover_orphan_syncs(
    session_factory: async_sessionmaker,
    schedule_fn,
    per_cycle_cap: int | None = None,
) -> int:
    """恢复孤儿同步记录（启动时与周期 sweeper 共用）。

    per_cycle_cap: 单次调用最多恢复的记录数，防止销售易长时间故障后积压
    大量 confirmed-pending 工单时无界 fan-out（每次调用无限创建协程任务）。
    """
    max_retries = settings.XIAOSHOUYI_SYNC_MAX_RETRIES
    if max_retries < 1:
        return 0

    SQL_CLAIM = text("""
        UPDATE workorder_review SET sync_status = 'syncing',
               sync_started_at = NOW(),
               sync_last_error = NULL,
               sync_idempotency_key = COALESCE(sync_idempotency_key, 'recover-' || id)
        WHERE id IN (
            SELECT id FROM workorder_review
            WHERE sync_status = 'pending'
              AND review_status = 'confirmed'
              AND sync_external_id IS NULL
              AND sync_attempts < :max_retries
            ORDER BY reviewed_at ASC
            LIMIT 50
            FOR UPDATE SKIP LOCKED
        )
        RETURNING id, sync_idempotency_key
    """)

    recovered = 0
    # 崩溃/超时遗留的 syncing 可能已经把 POST 发到销售易，禁止自动重发。
    # 扫描时先收敛为 uncertain，等待人工核实销售易是否已创建。
    try:
        async with session_factory() as db:
            await db.execute(text("""
                UPDATE workorder_review
                SET sync_status = 'uncertain',
                    sync_last_error = '同步任务异常中断，销售易结果需要人工核实'
                WHERE sync_status = 'syncing'
                  AND sync_external_id IS NULL
                  AND sync_started_at IS NOT NULL
                  AND sync_started_at < NOW() - (:stale_seconds * INTERVAL '1 second')
            """), {
                "stale_seconds": max(60.0, settings.XIAOSHOUYI_SYNC_TIMEOUT_SECONDS * 2),
            })
            await db.commit()
    except Exception:
        logger.exception("滞留同步状态收敛失败")

    while True:
        try:
            async with session_factory() as db:
                result = await db.execute(SQL_CLAIM, {
                    "max_retries": max_retries,
                    "stale_seconds": max(60.0, settings.XIAOSHOUYI_SYNC_TIMEOUT_SECONDS * 2),
                })
                batch = result.mappings().all()
                await db.commit()
        except Exception:
            logger.exception("孤儿同步记录查询失败")
            break

        if not batch:
            break

        # 已达本轮上限：本批次已认领（FOR UPDATE SKIP LOCKED）仍需调度，
        # 否则会卡 syncing 等 30 分钟；停止继续认领，剩余留待下轮
        cap_exceeded = per_cycle_cap is not None and recovered + len(batch) > per_cycle_cap

        for row in batch:
            wid = row["id"]
            idempotency_key = row.get("sync_idempotency_key") or f"recover-{wid}"
            try:
                schedule_fn(
                    background_sync_to_xiaoshouyi,
                    wid,
                    idempotency_key,
                    session_factory,
                    True,
                )
                recovered += 1
                logger.info("孤儿同步记录已恢复 workorder=%s key=%s", wid, idempotency_key)
            except Exception:
                logger.exception("孤儿同步记录恢复失败 workorder=%s", wid)

        if cap_exceeded:
            logger.info("周期扫描已达上限 %d 条，剩余记录留待下轮", per_cycle_cap)
            return recovered

    if recovered > 0:
        logger.info("孤儿同步记录恢复完成: %d 条", recovered)
    return recovered


class ReviewService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit_service = AuditService(db)
        self.bad_case_service = BadCaseService(db)
        self.lock_service = get_lock_service()

    @staticmethod
    def _request_hash(request: ConfirmRequest) -> str:
        payload = request.model_dump(
            mode="json", exclude={"idempotency_key", "lock_fencing_token"},
        )
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    async def get_idempotent_response(
        self, workorder_id: str, request: ConfirmRequest,
    ) -> dict | None:
        """在锁检查前查询，允许客户端安全重试已释放锁的成功请求。"""
        result = await self.db.execute(
            select(ReviewSubmission).where(
                or_(
                    ReviewSubmission.idempotency_key == request.idempotency_key,
                    (ReviewSubmission.workorder_id == workorder_id)
                    & (ReviewSubmission.session_id == request.session_id),
                )
            )
        )
        submissions = result.scalars().all()
        if not submissions:
            return None
        request_hash = self._request_hash(request)
        submission = next((item for item in submissions
                           if item.workorder_id == workorder_id
                           and item.request_hash == request_hash), None)
        if submission is None or len(submissions) > 1:
            raise HTTPException(status_code=409, detail="幂等键已被其他请求使用")
        return submission.response_data

    async def _merged_confirm_data(self, workorder_id: str, request: ConfirmRequest) -> dict:
        result = await self.db.execute(
            select(WorkOrderReview).where(WorkOrderReview.id == workorder_id)
        )
        review = result.scalar_one_or_none()
        if review is None:
            raise HTTPException(status_code=404, detail="工单不存在")
        ticket = await _get_ticket_dict(self.db, review.ticket_id)
        if ticket is None:
            raise HTTPException(status_code=422, detail={
                "message": "工单业务数据不存在", "valid": False,
                "blocking_count": 1, "warning_count": 0,
                "issues": [{"code": "SOURCE_DATA_MISSING", "severity": "blocking",
                            "field": None, "related_fields": [], "message": "工单业务数据不存在"}],
            })
        merged = {**ticket, **(review.field_overrides or {})}
        for change in request.changes:
            key = change.path.lstrip("/")
            if key in ALLOWED_FIELDS:
                if change.op == "remove":
                    merged[key] = None
                else:
                    merged[key] = change.new_value
        return merged

    async def release_lock_safely(
        self, workorder_id: str, operator_id: str, fencing_token: int | None = None,
    ) -> None:
        try:
            await self.lock_service.release(workorder_id, operator_id, fencing_token)
        except PermissionError:
            pass

    async def _raise_version_conflict(self, workorder_id: str) -> None:
        """409 冲突时返回服务端当前 version/review_status，供前端真实展示。"""
        row = await self.db.execute(
            text("SELECT version, review_status FROM workorder_review WHERE id = :id"),
            {"id": workorder_id},
        )
        r = row.mappings().first()
        raise HTTPException(status_code=409, detail={
            "message": "版本冲突，请刷新重试",
            "version": r["version"] if r else None,
            "review_status": r["review_status"] if r else None,
        })

    async def delete_stash(self, workorder_id: str) -> None:
        await self.db.execute(
            sa_delete(WorkOrderStash).where(WorkOrderStash.workorder_id == workorder_id)
        )

    async def review(
        self,
        *,
        workorder_id: str,
        request: ReviewRequest,
        operator_id: str,
        operator_name: str,
        operator_department: str,
    ) -> ConfirmResult:
        return await self.confirm(
            workorder_id=workorder_id,
            request=ConfirmRequest(
                session_id=request.session_id,
                version=request.version,
                changes=request.changes,
                reject_reason=request.reject_reason,
                review_notes=request.review_notes,
                idempotency_key=f"legacy-{request.session_id}",
                lock_fencing_token=request.lock_fencing_token,
            ),
            operator_id=operator_id,
            operator_name=operator_name,
            operator_department=operator_department,
            should_sync=True,
        )

    async def _execute_confirm(
        self, workorder_id, request, operator_id, operator_name, operator_department,
        fencing_token,
    ):
        # 乐观锁 UPDATE — confirmed 分支
        # 注意：reviewed_at 是 TIMESTAMP WITHOUT TZ，review_started_at 是
        # TIMESTAMPTZ。:now 只用于 CAST(:now AS timestamp) 一处，因此必须传
        # offset-naive datetime（datetime.utcnow()），否则 asyncpg 的 timestamp
        # 编码器无法处理 offset-aware datetime。
        # EXTRACT 中使用 PostgreSQL 内置 NOW() 函数（返回 TIMESTAMPTZ），
        # 与 review_started_at 类型一致，避免参数类型冲突。
        result = await self.db.execute(
            text("""
                UPDATE workorder_review
                SET review_status = 'confirmed', version = version + 1,
                    reviewed_at = CAST(:now AS timestamp), reviewed_by = :operator_name,
                    sync_status = 'pending', sync_attempts = 0,
                    sync_last_error = NULL, review_notes = :review_notes,
                    review_duration_seconds = CASE
                        WHEN review_started_at IS NOT NULL
                        THEN EXTRACT(EPOCH FROM (NOW() - review_started_at))::int
                        ELSE NULL
                    END
                WHERE id = :id AND version = :version
                  AND lock_fencing_token = :fencing_token
                  AND review_status IN ('pending_review', 'reviewing', 'stashed')
            """),
            {
                "id": workorder_id,
                "version": request.version,
                "now": datetime.now(timezone.utc).replace(tzinfo=None),
                "operator_name": operator_name,
                "review_notes": request.review_notes,
                "fencing_token": fencing_token,
            },
        )
        if result.rowcount == 0:
            await self._raise_version_conflict(workorder_id)

        # 白名单过滤 + 写入 field_overrides JSONB（而非直接 UPDATE 各列）
        filtered_changes = [
            c for c in request.changes
            if c.path.lstrip("/") in ALLOWED_FIELDS
        ]
        if filtered_changes:
            override_updates = {
                c.path.lstrip("/"): None if c.op == "remove" else c.new_value
                for c in filtered_changes
            }
            # 合并到现有 field_overrides
            await self.db.execute(
                text("""
                    UPDATE workorder_review
                    SET field_overrides = field_overrides || CAST(:updates AS jsonb)
                    WHERE id = :id
                """),
                {"id": workorder_id, "updates": json.dumps(override_updates, ensure_ascii=False)},
            )

        # 写入审计日志
        audit_logs = await self.audit_service.batch_create(
            workorder_id=workorder_id,
            session_id=request.session_id,
            changes=filtered_changes,
            operator_id=operator_id,
            operator_name=operator_name,
        )

        # bad_case 回流
        bad_case_count = 0
        if filtered_changes:
            audit_log_ids = [log.id for log in audit_logs]
            await self.bad_case_service.batch_create(
                workorder_id=workorder_id,
                audit_log_ids=audit_log_ids,
                changes=filtered_changes,
            )
            bad_case_count = len(filtered_changes)

        review_id = f"rev-{uuid.uuid4().hex[:12]}"
        await self.delete_stash(workorder_id)

        return {
            "review_id": review_id,
            "workorder_id": workorder_id,
            "status": "confirmed",
            "change_count": len(filtered_changes),
            "bad_case_count": bad_case_count,
            "next_review_status": "dispatching",
        }

    async def _execute_reject(
        self, workorder_id, request, operator_id, operator_name, fencing_token,
    ):
        result = await self.db.execute(
            text("""
                UPDATE workorder_review
                SET review_status = 'pending_review', version = version + 1,
                    reject_count = reject_count + 1,
                    last_reject_reason = :reason,
                    last_rejected_by = :operator_name,
                    last_rejected_at = CAST(:now AS timestamp),
                    review_notes = :review_notes,
                    sync_status = 'pending', sync_attempts = 0,
                    sync_last_error = NULL,
                    review_started_at = NULL,
                    review_duration_seconds = NULL
                WHERE id = :id AND version = :version
                  AND lock_fencing_token = :fencing_token
                  AND review_status IN ('pending_review', 'reviewing', 'stashed')
            """),
            {
                "id": workorder_id,
                "version": request.version,
                "reason": request.reject_reason,
                "operator_name": operator_name,
                "now": datetime.now(timezone.utc).replace(tzinfo=None),
                "review_notes": request.review_notes or request.reject_reason,
                "fencing_token": fencing_token,
            },
        )
        if result.rowcount == 0:
            await self._raise_version_conflict(workorder_id)

        await self.audit_service.create_reject_log(
            workorder_id=workorder_id,
            session_id=request.session_id,
            reject_reason=request.reject_reason,
            operator_id=operator_id,
            operator_name=operator_name,
        )

        await self.delete_stash(workorder_id)

        review_id = f"rev-{uuid.uuid4().hex[:12]}"
        return {
            "review_id": review_id,
            "workorder_id": workorder_id,
            "status": "rejected",
            "change_count": 0,
            "bad_case_count": 0,
            "next_review_status": "pending_review",
        }

    async def confirm(
        self,
        *,
        workorder_id: str,
        request: ConfirmRequest,
        operator_id: str,
        operator_name: str,
        operator_department: str,
        should_sync: bool = True,
    ) -> ConfirmResult:
        """确认提交流程：本地落库 + 可选后台同步销售易。"""
        existing = await self.get_idempotent_response(workorder_id, request)
        if existing is not None:
            return ConfirmResult(response=existing, sync_idempotency_key=None)
        # SELECT 会触发 SQLAlchemy autobegin；实际提交使用一个全新事务。
        await self.db.rollback()

        completed = False
        try:
            async with self.db.begin():
                owner = await self.lock_service.get_owner(workorder_id)
                if (owner is None or owner["operator_id"] != operator_id
                        or owner.get("fencing_token") != request.lock_fencing_token):
                    raise HTTPException(status_code=423, detail="编辑锁已失效")
                fencing_token = request.lock_fencing_token
                if request.reject_reason is not None:
                    result_dict = await self._execute_reject(
                        workorder_id, request, operator_id, operator_name, fencing_token,
                    )
                    result_dict["sync_status"] = "pending"
                else:
                    merged = await self._merged_confirm_data(workorder_id, request)
                    validation = validate_workorder(merged)
                    if not validation.valid and settings.REVIEW_VALIDATION_MODE == "enforce":
                        raise HTTPException(status_code=422, detail={
                            "message": "工单存在阻断问题，无法确认",
                            **validation.model_dump(mode="json"),
                        })
                    result_dict = await self._execute_confirm(
                        workorder_id, request, operator_id, operator_name, operator_department,
                        fencing_token,
                    )

                result_dict.setdefault("sync_status", "pending")
                self.db.add(ReviewSubmission(
                    idempotency_key=request.idempotency_key,
                    workorder_id=workorder_id,
                    session_id=request.session_id,
                    decision="rejected" if request.reject_reason is not None else "confirmed",
                    request_hash=self._request_hash(request),
                    response_data=result_dict,
                    operator_id=operator_id,
                ))
            completed = True
        except IntegrityError:
            await self.db.rollback()
            existing = await self.get_idempotent_response(workorder_id, request)
            if existing is None:
                raise
            return ConfirmResult(response=existing, sync_idempotency_key=None)
        finally:
            if completed:
                await self.release_lock_safely(
                    workorder_id, operator_id, request.lock_fencing_token,
                )

        sync_key: str | None = None
        if should_sync and result_dict.get("status") == "confirmed":
            result_dict["sync_status"] = "pending"
            sync_key = request.idempotency_key
        logger.info(
            "review_decision workorder=%s session=%s operator=%s decision=%s changes=%d "
            "version=%d fencing_token=%d sync=%s",
            workorder_id, request.session_id, operator_id, result_dict["status"],
            result_dict["change_count"], request.version, request.lock_fencing_token,
            result_dict.get("sync_status"),
        )
        return ConfirmResult(response=result_dict, sync_idempotency_key=sync_key)

    def _build_existing_response(self, workorder_id, request):
        return {
            "review_id": "dup",
            "workorder_id": workorder_id,
            "status": "confirmed" if request.reject_reason is None else "rejected",
            "change_count": 0,
            "bad_case_count": 0,
            "next_review_status": "dispatching" if request.reject_reason is None else "pending_review",
        }
