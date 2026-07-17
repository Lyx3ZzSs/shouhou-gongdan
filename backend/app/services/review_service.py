import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from fastapi import HTTPException
from app.schemas.review import ReviewRequest, ReviewResponse, ALLOWED_FIELDS
from app.services.audit_service import AuditService
from app.services.bad_case_service import BadCaseService
from app.services.lock_service import LockService


class ReviewService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit_service = AuditService(db)
        self.bad_case_service = BadCaseService(db)
        self.lock_service = LockService()

    async def review(
        self,
        *,
        workorder_id: str,
        request: ReviewRequest,
        operator_id: str,
        operator_name: str,
        operator_department: str,
    ) -> dict:
        # 事务块，包裹幂等检查 + 全部写入操作，保证原子性
        async with self.db.begin():
            # 1. 幂等性检查
            result = await self.db.execute(
                text("SELECT id FROM workorder_audit_log WHERE session_id = :sid LIMIT 1"),
                {"sid": request.session_id},
            )
            if result.scalar():
                return self._build_existing_response(workorder_id, request)

            if request.reject_reason is not None:
                return await self._execute_reject(
                    workorder_id, request, operator_id, operator_name
                )
            else:
                return await self._execute_confirm(
                    workorder_id, request, operator_id, operator_name, operator_department
                )

    async def _execute_confirm(self, workorder_id, request, operator_id, operator_name, operator_department):
        # 2. 乐观锁 UPDATE — confirmed 分支
        result = await self.db.execute(
            text("""
                UPDATE workorder
                SET status = 'confirmed', version = version + 1,
                    reviewed_at = :now, reviewed_by = :operator_name
                WHERE id = :id AND version = :version AND status = 'pending_review'
            """),
            {
                "id": workorder_id,
                "version": request.version,
                "now": datetime.utcnow(),
                "operator_name": operator_name,
            },
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=409, detail="版本冲突，请刷新重试")

        # 3. 白名单过滤 + 更新变更字段
        filtered_changes = [
            c for c in request.changes
            if c.path.lstrip("/") in ALLOWED_FIELDS
        ]
        for c in filtered_changes:
            field_name = c.path.lstrip("/")
            await self.db.execute(
                text(f"UPDATE workorder SET {field_name} = :val WHERE id = :id"),
                {"val": c.new_value, "id": workorder_id},
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

        # 6. 释放编辑锁
        await self.lock_service.release(workorder_id, operator_id)

        review_id = f"rev-{uuid.uuid4().hex[:12]}"
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
                    last_rejected_at = :now
                WHERE id = :id AND version = :version AND status = 'pending_review'
            """),
            {
                "id": workorder_id,
                "version": request.version,
                "reason": request.reject_reason,
                "operator_name": operator_name,
                "now": datetime.utcnow(),
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

        # 释放锁
        await self.lock_service.release(workorder_id, operator_id)

        review_id = f"rev-{uuid.uuid4().hex[:12]}"
        return {
            "review_id": review_id,
            "workorder_id": workorder_id,
            "status": "rejected",
            "change_count": 0,
            "bad_case_count": 0,
            "next_status": "pending_review",
        }

    def _build_existing_response(self, workorder_id, request):
        return {
            "review_id": "dup",
            "workorder_id": workorder_id,
            "status": "confirmed" if request.reject_reason is None else "rejected",
            "change_count": 0,
            "bad_case_count": 0,
            "next_status": "dispatching" if request.reject_reason is None else "pending_review",
        }
