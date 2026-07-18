from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import WorkOrderAuditLog
from app.schemas.review import FieldChange


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def batch_create(
        self,
        *,
        workorder_id: str,
        session_id: str,
        changes: list[FieldChange],
        operator_id: str,
        operator_name: str,
        change_type: str = "replace",
    ) -> list[WorkOrderAuditLog]:
        now = datetime.utcnow()
        logs = [
            WorkOrderAuditLog(
                workorder_id=workorder_id,
                session_id=session_id,
                field_path=c.path,
                field_label=c.field_label,
                old_value=str(c.old_value) if c.old_value is not None else None,
                new_value=str(c.new_value) if c.new_value is not None else None,
                change_type=c.op,
                operator_id=operator_id,
                operator_name=operator_name,
                operated_at=now,
            )
            for c in changes
        ]
        self.db.add_all(logs)
        await self.db.flush()
        return logs

    async def create_reject_log(
        self,
        *,
        workorder_id: str,
        session_id: str,
        reject_reason: str,
        operator_id: str,
        operator_name: str,
    ):
        log = WorkOrderAuditLog(
            workorder_id=workorder_id,
            session_id=session_id,
            field_path="/_rejected",
            field_label="退回重填",
            old_value=None,
            new_value=reject_reason,
            change_type="rejected",
            operator_id=operator_id,
            operator_name=operator_name,
            operated_at=datetime.utcnow(),
        )
        self.db.add(log)
        await self.db.flush()
