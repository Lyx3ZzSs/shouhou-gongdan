import asyncio
import logging
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, update, delete as sa_delete
from fastapi import HTTPException
from app.schemas.review import ReviewRequest, ConfirmRequest, ALLOWED_FIELDS
from app.models.workorder import WorkOrder
from app.models.workorder_stash import WorkOrderStash
from app.services.audit_service import AuditService
from app.services.bad_case_service import BadCaseService
from app.services.lock_service import get_lock_service
from app.clients.xiaoshouyi import (
    get_xiaoshouyi_client,
    CreateWorkOrderRequest,
)

logger = logging.getLogger(__name__)


class ReviewService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit_service = AuditService(db)
        self.bad_case_service = BadCaseService(db)
        self.lock_service = get_lock_service()

    async def release_lock_safely(self, workorder_id: str, operator_id: str) -> None:
        """释放编辑锁，忽略 PermissionError（锁可能已过期）。"""
        try:
            await self.lock_service.release(workorder_id, operator_id)
        except PermissionError:
            pass

    async def delete_stash(self, workorder_id: str) -> None:
        """清除暂存数据（工单已确认/驳回，不再需要草稿）。"""
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
    ) -> dict:
        """提交审核（保留兼容旧 /review 端点）。"""
        try:
            async with self.db.begin():
                # 1. 幂等性检查
                result = await self.db.execute(
                    text("SELECT id FROM workorder_audit_log WHERE session_id = :sid LIMIT 1"),
                    {"sid": request.session_id},
                )
                if result.scalar():
                    return self._build_existing_response(workorder_id, request)

                if request.reject_reason is not None:
                    result_dict = await self._execute_reject(
                        workorder_id, request, operator_id, operator_name
                    )
                else:
                    result_dict = await self._execute_confirm(
                        workorder_id, request, operator_id, operator_name, operator_department
                    )
                # 事务在此处提交（async with 退出时）
        finally:
            await self.release_lock_safely(workorder_id, operator_id)

        return result_dict

    async def _execute_confirm(
        self, workorder_id, request, operator_id, operator_name, operator_department,
    ):
        # 2. 乐观锁 UPDATE — confirmed 分支，sync_status = 'pending'
        result = await self.db.execute(
            text("""
                UPDATE workorder
                SET status = 'confirmed', version = version + 1,
                    reviewed_at = :now, reviewed_by = :operator_name,
                    sync_status = 'pending', review_notes = :review_notes
                WHERE id = :id AND version = :version AND status != 'confirmed'
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

        # 3. 白名单过滤 + 批量更新变更字段（合并为一次 UPDATE）
        filtered_changes = [
            c for c in request.changes
            if c.path.lstrip("/") in ALLOWED_FIELDS
        ]
        if filtered_changes:
            values = {c.path.lstrip("/"): c.new_value for c in filtered_changes}
            await self.db.execute(
                update(WorkOrder)
                .where(WorkOrder.id == workorder_id)
                .values(**values),
            )

        # 4. 写入审计日志
        audit_logs = await self.audit_service.batch_create(
            workorder_id=workorder_id,
            session_id=request.session_id,
            changes=filtered_changes,
            operator_id=operator_id,
            operator_name=operator_name,
        )

        # 5. bad_case 回流（仅 confirmed + 有变更时）
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

        # 6. 清除暂存数据
        await self.delete_stash(workorder_id)

        return {
            "review_id": review_id,
            "workorder_id": workorder_id,
            "status": "confirmed",
            "change_count": len(filtered_changes),
            "bad_case_count": bad_case_count,
            "next_status": "dispatching",
        }

    async def _execute_reject(self, workorder_id, request, operator_id, operator_name):
        result = await self.db.execute(
            text("""
                UPDATE workorder
                SET status = 'pending_review', version = version + 1,
                    reject_count = reject_count + 1,
                    last_reject_reason = :reason,
                    last_rejected_by = :operator_name,
                    last_rejected_at = :now,
                    review_notes = :review_notes
                WHERE id = :id AND version = :version AND status != 'confirmed'
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

        # 清除暂存数据
        await self.delete_stash(workorder_id)

        review_id = f"rev-{uuid.uuid4().hex[:12]}"
        return {
            "review_id": review_id,
            "workorder_id": workorder_id,
            "status": "rejected",
            "change_count": 0,
            "bad_case_count": 0,
            "next_status": "pending_review",
        }

    async def confirm(
        self,
        *,
        workorder_id: str,
        request: ConfirmRequest,
        operator_id: str,
        operator_name: str,
        operator_department: str,
    ) -> dict:
        """确认提交流程：本地落库 + 后台异步同步销售易。"""
        idempotent = False
        try:
            async with self.db.begin():
                # 1. 幂等性检查
                result = await self.db.execute(
                    text("SELECT id FROM workorder_audit_log WHERE session_id = :sid LIMIT 1"),
                    {"sid": request.session_id},
                )
                if result.scalar():
                    # 幂等重试 — 仍清除暂存数据
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
                # 事务在此处提交（async with 退出时）
        finally:
            await self.release_lock_safely(workorder_id, operator_id)

        # 同步至销售易（事务外 + 锁释放后，5s 超时，失败不阻塞确认返回）
        if not idempotent and result_dict.get("status") == "confirmed":
            sync_status = await self._sync_to_xiaoshouyi(workorder_id, request.idempotency_key)
            result_dict["sync_status"] = sync_status

        return result_dict

    async def _sync_to_xiaoshouyi(self, workorder_id: str, idempotency_key: str) -> str:
        """调用销售易创建工单，返回 sync_status。

        内联执行（非 fire-and-forget），5s 超时。失败时更新 DB 为 'failed'，
        但不抛出异常——确认提交本身仍然成功，仅标记同步状态。
        """
        try:
            client = get_xiaoshouyi_client()
            req = CreateWorkOrderRequest(idempotency_key=idempotency_key)
            sync_result = await asyncio.wait_for(
                client.create_work_order(req),
                timeout=5.0,
            )
            # 成功 → 标记 synced
            if sync_result.external_id:
                await self.db.execute(
                    update(WorkOrder)
                    .where(WorkOrder.id == workorder_id)
                    .values(sync_status='synced'),
                )
                logger.info("销售易同步成功 workorder=%s external_id=%s", workorder_id, sync_result.external_id)
                return 'synced'
            else:
                # 客户端未配置（占位实现返回 external_id=None）
                logger.info("销售易客户端未实现或未配置，workorder=%s", workorder_id)
                return 'pending'
        except asyncio.TimeoutError:
            logger.error("销售易同步超时 workorder=%s", workorder_id)
            await self.db.execute(
                update(WorkOrder)
                .where(WorkOrder.id == workorder_id)
                .values(sync_status='failed'),
            )
            return 'failed'
        except NotImplementedError:
            logger.info("销售易客户端未实现，跳过同步 workorder=%s", workorder_id)
            return 'pending'
        except Exception:
            logger.exception("销售易同步失败 workorder=%s", workorder_id)
            await self.db.execute(
                update(WorkOrder)
                .where(WorkOrder.id == workorder_id)
                .values(sync_status='failed'),
            )
            return 'failed'

    def _build_existing_response(self, workorder_id, request):
        return {
            "review_id": "dup",
            "workorder_id": workorder_id,
            "status": "confirmed" if request.reject_reason is None else "rejected",
            "change_count": 0,
            "bad_case_count": 0,
            "next_status": "dispatching" if request.reject_reason is None else "pending_review",
        }
