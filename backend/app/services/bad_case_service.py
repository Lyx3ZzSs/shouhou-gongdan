from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.bad_case import BadCaseSample
from app.schemas.review import FieldChange


class BadCaseService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def batch_create(
        self,
        *,
        workorder_id: str,
        audit_log_ids: list[int],
        changes: list[FieldChange],
    ):
        now = datetime.utcnow()
        samples = [
            BadCaseSample(
                workorder_id=workorder_id,
                audit_log_id=audit_log_id,
                field_path=c.path,
                ai_value=str(c.old_value) if c.old_value is not None else None,
                human_value=str(c.new_value) if c.new_value is not None else None,
                sample_status="pending",
                source="review_correction",
                created_at=now,
            )
            for c, audit_log_id in zip(changes, audit_log_ids)
        ]
        self.db.add_all(samples)
        await self.db.flush()
