import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import text, update, delete as sa_delete, select
from fastapi import HTTPException
from app.schemas.review import ReviewRequest, ConfirmRequest, ALLOWED_FIELDS
from app.models.workorder import WorkOrderReview
from app.models.ticket import VTicket
from app.models.workorder_stash import WorkOrderStash
from app.services.audit_service import AuditService
from app.services.bad_case_service import BadCaseService
from app.services.lock_service import get_lock_service
from app.core.config import settings
from app.clients.xiaoshouyi import (
    get_xiaoshouyi_client,
    CreateWorkOrderRequest,
)

logger = logging.getLogger(__name__)


@dataclass
class ConfirmResult:
    """confirm() 返回结构：分离响应字段与后台同步调度信息。"""
    response: dict  # 可直接解包传入 ConfirmResponse(**response)
    sync_idempotency_key: str | None = None  # None = 无需后台同步


async def _get_ticket_dict(db: AsyncSession, ticket_no: str) -> dict | None:
    """从 v_ticket 视图获取工单业务数据。"""
    result = await db.execute(
        select(VTicket).where(VTicket.ticket_no == ticket_no)
    )
    ticket = result.scalar_one_or_none()
    if ticket is None:
        return None
    return ticket.to_dict()


async def background_sync_to_xiaoshouyi(
    workorder_id: str,
    sync_idempotency_key: str,
    session_factory: async_sessionmaker,
) -> str:
    """后台同步至销售易：merge v_ticket + field_overrides → API。"""
    max_retries = settings.XIAOSHOUYI_SYNC_MAX_RETRIES
    timeout = settings.XIAOSHOUYI_SYNC_TIMEOUT_SECONDS
    if max_retries < 1:
        logger.warning("销售易同步已禁用（XIAOSHOUYI_SYNC_MAX_RETRIES=%d），workorder=%s", max_retries, workorder_id)
        return 'pending'

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            # ---- 原子认领 ----
            async with session_factory() as db:
                claim_result = await db.execute(
                    text("""
                        UPDATE workorder_review
                        SET sync_status = 'syncing',
                            sync_attempts = :attempt,
                            sync_idempotency_key = :key,
                            sync_started_at = NOW()
                        WHERE id = :id
                          AND sync_external_id IS NULL
                          AND (sync_status != 'syncing' OR sync_idempotency_key = :key)
                    """),
                    {"id": workorder_id, "attempt": attempt, "key": sync_idempotency_key},
                )
                if claim_result.rowcount == 0:
                    check = await db.execute(
                        text("SELECT sync_external_id FROM workorder_review WHERE id = :id"),
                        {"id": workorder_id},
                    )
                    ext_row = check.mappings().first()
                    if ext_row and ext_row.get("sync_external_id"):
                        logger.info("原子认领跳过（已有 external_id）workorder=%s ext=%s",
                                    workorder_id, ext_row["sync_external_id"])
                        return 'synced'
                    logger.warning("原子认领失败但 external_id 为空 workorder=%s", workorder_id)
                    return 'failed'
                await db.commit()

            # ---- 读取审核记录 + v_ticket 业务数据 ----
            async with session_factory() as db:
                result = await db.execute(
                    text("SELECT * FROM workorder_review WHERE id = :id"),
                    {"id": workorder_id},
                )
                row = result.mappings().first()
                if row is None:
                    logger.error("销售易同步失败: 审核记录 %s 不存在", workorder_id)
                    return 'failed'

                ticket_no = row.get("ticket_no")
                overrides = row.get("field_overrides") or {}

                # 获取 v_ticket 业务数据
                ticket_dict = await _get_ticket_dict(db, ticket_no)
                if ticket_dict is None:
                    logger.error("销售易同步失败: ticket_no=%s 在 v_ticket 中不存在", ticket_no)
                    return 'failed'

                # merge: v_ticket 原始值 + field_overrides 覆盖
                from app.clients.xiaoshouyi import map_db_to_xiaoshouyi
                merged = {**ticket_dict, **overrides}
                req = map_db_to_xiaoshouyi(merged, sync_idempotency_key)

            # ---- 调用销售易 API ----
            client = get_xiaoshouyi_client()
            sync_result = await asyncio.wait_for(
                client.create_work_order(req),
                timeout=timeout,
            )

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
                    await db.execute(
                        update(WorkOrderReview)
                        .where(WorkOrderReview.id == workorder_id)
                        .values(sync_status='pending', sync_attempts=0, sync_last_error=None),
                    )
                    await db.commit()
                    logger.info("销售易客户端未实现或未配置，workorder=%s", workorder_id)
                    return 'pending'
        except asyncio.CancelledError:
            logger.info("销售易同步被取消 workorder=%s attempt=%d", workorder_id, attempt)
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
        except (asyncio.TimeoutError, NotImplementedError) as e:
            last_error = str(e)
            logger.warning("销售易同步失败 workorder=%s attempt=%d/%d: %s",
                           workorder_id, attempt, max_retries, last_error)
        except Exception as e:
            last_error = str(e)
            logger.exception("销售易同步异常 workorder=%s attempt=%d/%d", workorder_id, attempt, max_retries)

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
) -> int:
    """启动时恢复孤儿同步记录。"""
    max_retries = settings.XIAOSHOUYI_SYNC_MAX_RETRIES
    if max_retries < 1:
        return 0

    SQL_CLAIM = text("""
        UPDATE workorder_review SET sync_status = 'syncing',
               sync_started_at = NOW(),
               sync_idempotency_key = COALESCE(sync_idempotency_key, 'recover-' || id)
        WHERE id IN (
            SELECT id FROM workorder_review
            WHERE (
                sync_status = 'pending'
                OR (
                    sync_status = 'syncing'
                    AND sync_started_at IS NOT NULL
                    AND sync_started_at < NOW() - INTERVAL '30 minutes'
                )
            )
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
    while True:
        try:
            async with session_factory() as db:
                result = await db.execute(SQL_CLAIM, {"max_retries": max_retries})
                batch = result.mappings().all()
                await db.commit()
        except Exception:
            logger.exception("孤儿同步记录查询失败")
            break

        if not batch:
            break

        for row in batch:
            wid = row["id"]
            idempotency_key = row.get("sync_idempotency_key") or f"recover-{wid}"
            try:
                schedule_fn(
                    background_sync_to_xiaoshouyi,
                    wid,
                    idempotency_key,
                    session_factory,
                )
                recovered += 1
                logger.info("孤儿同步记录已恢复 workorder=%s key=%s", wid, idempotency_key)
            except Exception:
                logger.exception("孤儿同步记录恢复失败 workorder=%s", wid)

    if recovered > 0:
        logger.info("孤儿同步记录恢复完成: %d 条", recovered)
    return recovered


class ReviewService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit_service = AuditService(db)
        self.bad_case_service = BadCaseService(db)
        self.lock_service = get_lock_service()

    async def release_lock_safely(self, workorder_id: str, operator_id: str) -> None:
        try:
            await self.lock_service.release(workorder_id, operator_id)
        except PermissionError:
            pass

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
            ),
            operator_id=operator_id,
            operator_name=operator_name,
            operator_department=operator_department,
            should_sync=True,
        )

    async def _execute_confirm(
        self, workorder_id, request, operator_id, operator_name, operator_department,
    ):
        # 乐观锁 UPDATE — confirmed 分支
        result = await self.db.execute(
            text("""
                UPDATE workorder_review
                SET review_status = 'confirmed', version = version + 1,
                    reviewed_at = :now, reviewed_by = :operator_name,
                    sync_status = 'pending', sync_attempts = 0,
                    sync_last_error = NULL, review_notes = :review_notes,
                    review_duration_seconds = CASE
                        WHEN review_started_at IS NOT NULL
                        THEN EXTRACT(EPOCH FROM (:now - review_started_at))::int
                        ELSE NULL
                    END
                WHERE id = :id AND version = :version AND review_status != 'confirmed'
            """),
            {
                "id": workorder_id,
                "version": request.version,
                "now": datetime.utcnow(),
                "operator_name": operator_name,
                "review_notes": request.review_notes,
            },
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=409, detail="版本冲突，请刷新重试")

        # 白名单过滤 + 写入 field_overrides JSONB（而非直接 UPDATE 各列）
        filtered_changes = [
            c for c in request.changes
            if c.path.lstrip("/") in ALLOWED_FIELDS
        ]
        if filtered_changes:
            override_updates = {c.path.lstrip("/"): c.new_value for c in filtered_changes}
            # 合并到现有 field_overrides
            await self.db.execute(
                text("""
                    UPDATE workorder_review
                    SET field_overrides = field_overrides || :updates::jsonb
                    WHERE id = :id
                """),
                {"id": workorder_id, "updates": str(override_updates)},
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

    async def _execute_reject(self, workorder_id, request, operator_id, operator_name):
        result = await self.db.execute(
            text("""
                UPDATE workorder_review
                SET review_status = 'pending_review', version = version + 1,
                    reject_count = reject_count + 1,
                    last_reject_reason = :reason,
                    last_rejected_by = :operator_name,
                    last_rejected_at = :now,
                    review_notes = :review_notes,
                    sync_status = 'pending', sync_attempts = 0,
                    sync_last_error = NULL,
                    review_duration_seconds = CASE
                        WHEN review_started_at IS NOT NULL
                        THEN EXTRACT(EPOCH FROM (:now - review_started_at))::int
                        ELSE NULL
                    END
                WHERE id = :id AND version = :version AND review_status != 'confirmed'
            """),
            {
                "id": workorder_id,
                "version": request.version,
                "reason": request.reject_reason,
                "operator_name": operator_name,
                "now": datetime.utcnow(),
                "review_notes": request.review_notes or request.reject_reason,
            },
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=409, detail="版本冲突，请刷新重试")

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
        idempotent = False
        try:
            async with self.db.begin():
                result = await self.db.execute(
                    text("SELECT id FROM workorder_audit_log WHERE session_id = :sid LIMIT 1"),
                    {"sid": request.session_id},
                )
                if result.scalar():
                    await self.delete_stash(workorder_id)
                    idempotent = True
                    result_dict = {
                        **self._build_existing_response(workorder_id, request),
                        "sync_status": "pending",
                    }
                elif request.reject_reason is not None:
                    result_dict = await self._execute_reject(
                        workorder_id, request, operator_id, operator_name
                    )
                    result_dict["sync_status"] = "pending"
                else:
                    result_dict = await self._execute_confirm(
                        workorder_id, request, operator_id, operator_name, operator_department,
                    )
        finally:
            await self.release_lock_safely(workorder_id, operator_id)

        sync_key: str | None = None
        if should_sync and not idempotent and result_dict.get("status") == "confirmed":
            result_dict["sync_status"] = "pending"
            sync_key = request.idempotency_key
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
