import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import text, update, delete as sa_delete
from fastapi import HTTPException
from app.schemas.review import ReviewRequest, ConfirmRequest, ALLOWED_FIELDS
from app.models.workorder import WorkOrder
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


async def background_sync_to_xiaoshouyi(
    workorder_id: str,
    sync_idempotency_key: str,
    session_factory: async_sessionmaker,
) -> str:
    """后台同步至销售易（非阻塞，带指数退避重试）。

    由 FastAPI BackgroundTasks 调度执行。使用独立的 DB session，
    从数据库读取工单最新数据后调用销售易 insertServiceCase 接口。
    """
    max_retries = settings.XIAOSHOUYI_SYNC_MAX_RETRIES
    timeout = settings.XIAOSHOUYI_SYNC_TIMEOUT_SECONDS
    if max_retries < 1:
        logger.warning("销售易同步已禁用（XIAOSHOUYI_SYNC_MAX_RETRIES=%d），workorder=%s", max_retries, workorder_id)
        return 'pending'
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            async with session_factory() as db:
                # 读取工单最新数据
                result = await db.execute(
                    text("SELECT * FROM workorder WHERE id = :id"),
                    {"id": workorder_id},
                )
                row = result.mappings().first()
                if row is None:
                    logger.error("销售易同步失败: 工单 %s 不存在", workorder_id)
                    return 'failed'

                # 构建销售易 API 请求体
                req = CreateWorkOrderRequest(
                    ownerId=row.get("ownerId") or "",
                    dimDepart=row.get("dimDepart") or "",
                    entityType=row.get("entityType") or "11010045500001",
                    name=row.get("name") or "",
                    caseSource=row.get("caseSource") or "",
                    feedbackChannel__c=row.get("feedbackChannel__c") or "",
                    workOrderStatus__c=row.get("workOrderStatus__c") or "",
                    caseDescription=row.get("caseDescription") or "",
                    caseStatus=row.get("caseStatus") or "",
                    caseAccountId=row.get("caseAccountId") or "",
                    custLevel1__c=row.get("custLevel1__c") or "",
                    projectName__c=row.get("projectName__c") or "",
                    projectProvince__c=row.get("projectProvince__c") or "",
                    bigCustShortName__c=row.get("bigCustShortName__c") or "",
                    serviceCycleStart__c=row.get("serviceCycleStart__c") or "",
                    serviceCycleEnd__c=row.get("serviceCycleEnd__c") or "",
                    isOfflineApply__c=row.get("isOfflineApply__c") or "",
                    isOverdueService__c=row.get("isOverdueService__c") or "",
                    problemLevel__c=row.get("problemLevel__c") or "",
                    problemType1__c=row.get("problemType1__c") or "",
                    problemType2__c=row.get("problemType2__c") or "",
                    problemType3__c=row.get("problemType3__c") or "",
                    feedbackCount__c=row.get("feedbackCount__c") or "",
                    problemResponsible__c=row.get("problemResponsible__c") or "",
                    problemDept__c=row.get("problemDept__c") or "",
                    feedbackUserName__c=row.get("feedbackUserName__c") or "",
                    feedbackUserContact__c=row.get("feedbackUserContact__c") or "",
                    needCallBack__c=row.get("needCallBack__c") or "",
                    isHandled__c=row.get("isHandled__c") or "",
                    needOnSite__c=row.get("needOnSite__c") or "",
                    remark__c=row.get("remark__c") or "",
                    planFeedbackTime__c=row.get("planFeedbackTime__c") or "",
                    requireSolveTime__c=row.get("requireSolveTime__c") or "",
                    relatedAttachment__c=row.get("relatedAttachment__c") or "",
                    defectFlag__c=row.get("defectFlag__c") or "1",
                )

                # 更新尝试计数
                if attempt == 1:
                    await db.execute(
                        update(WorkOrder)
                        .where(WorkOrder.id == workorder_id)
                        .values(sync_status='syncing', sync_attempts=attempt),
                    )
                else:
                    await db.execute(
                        update(WorkOrder)
                        .where(WorkOrder.id == workorder_id)
                        .values(sync_attempts=attempt),
                    )
                await db.commit()

                client = get_xiaoshouyi_client()
                sync_result = await asyncio.wait_for(
                    client.create_work_order(req),
                    timeout=timeout,
                )

                if sync_result.external_id:
                    await db.execute(
                        update(WorkOrder)
                        .where(WorkOrder.id == workorder_id)
                        .values(sync_status='synced', sync_attempts=attempt),
                    )
                    await db.commit()
                    logger.info("销售易同步成功 workorder=%s external_id=%s attempt=%d", workorder_id, sync_result.external_id, attempt)
                    return 'synced'
                else:
                    await db.execute(
                        update(WorkOrder)
                        .where(WorkOrder.id == workorder_id)
                        .values(sync_status='pending', sync_attempts=0, sync_last_error=None),
                    )
                    await db.commit()
                    logger.info("销售易客户端未实现或未配置，workorder=%s", workorder_id)
                    return 'pending'
        except asyncio.CancelledError:
            # 服务关闭时的取消信号 — 尝试将状态重置为 pending 以避免孤儿记录
            logger.info("销售易同步被取消 workorder=%s attempt=%d", workorder_id, attempt)
            try:
                async with session_factory() as db:
                    await db.execute(
                        update(WorkOrder)
                        .where(WorkOrder.id == workorder_id)
                        .values(sync_status='pending', sync_attempts=0, sync_last_error=None),
                    )
                    await db.commit()
            except Exception:
                logger.warning("销售易同步取消后状态重置失败 workorder=%s", workorder_id, exc_info=True)
            raise
        except (asyncio.TimeoutError, NotImplementedError) as e:
            last_error = str(e)
            logger.warning("销售易同步失败 workorder=%s attempt=%d/%d: %s", workorder_id, attempt, max_retries, last_error)
        except Exception as e:
            last_error = str(e)
            logger.exception("销售易同步异常 workorder=%s attempt=%d/%d", workorder_id, attempt, max_retries)

        if attempt >= max_retries:
            try:
                async with session_factory() as db:
                    await db.execute(
                        update(WorkOrder)
                        .where(WorkOrder.id == workorder_id)
                        .values(sync_status='failed', sync_attempts=attempt, sync_last_error=last_error),
                    )
                    await db.commit()
                logger.error("销售易同步最终失败 workorder=%s after %d attempts: %s", workorder_id, max_retries, last_error)
            except Exception:
                logger.exception("销售易同步失败状态写入异常 workorder=%s", workorder_id)
            return 'failed'

        # 指数退避：2s, 4s（第三次重试失败后直接标记 failed，不等待）
        backoff = 2 ** attempt
        logger.info("销售易同步重试 workorder=%s 等待 %ds 后进行第 %d 次重试", workorder_id, backoff, attempt + 1)
        try:
            await asyncio.sleep(backoff)
        except asyncio.CancelledError:
            logger.info("销售易同步在退避等待期间被取消 workorder=%s attempt=%d", workorder_id, attempt)
            try:
                async with session_factory() as db:
                    await db.execute(
                        update(WorkOrder)
                        .where(WorkOrder.id == workorder_id)
                        .values(sync_status='pending', sync_attempts=0, sync_last_error=None),
                    )
                    await db.commit()
            except Exception:
                logger.warning("销售易同步取消后状态重置失败 workorder=%s", workorder_id, exc_info=True)
            raise


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
    ) -> ConfirmResult:
        """提交审核（已废弃，委托给 confirm 逻辑）。"""
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
        # 2. 乐观锁 UPDATE — confirmed 分支，sync_status = 'pending'
        result = await self.db.execute(
            text("""
                UPDATE workorder
                SET status = 'confirmed', version = version + 1,
                    reviewed_at = :now, reviewed_by = :operator_name,
                    sync_status = 'pending', sync_attempts = 0,
                    sync_last_error = NULL, review_notes = :review_notes
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
                    review_notes = :review_notes,
                    sync_status = 'pending', sync_attempts = 0,
                    sync_last_error = NULL
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
        should_sync: bool = True,
    ) -> ConfirmResult:
        """确认提交流程：本地落库 + 可选后台同步销售易。

        返回 ConfirmResult，其中 sync_idempotency_key 非 None 表示需要后台同步。
        若无需同步（如幂等重试、拒绝操作），sync_idempotency_key 为 None。
        """
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

        # 同步至销售易由 BackgroundTasks 异步调度（见 router 层），
        # 此处仅返回 sync_status='pending'，实际同步在响应返回后执行。
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
            "next_status": "dispatching" if request.reject_reason is None else "pending_review",
        }
