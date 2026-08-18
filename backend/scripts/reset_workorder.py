"""重置测试工单为待审核状态"""
import asyncio
from app.core.database import async_session
from sqlalchemy import text

async def reset():
    async with async_session() as db:
        await db.execute(text('''
            UPDATE workorder_review SET review_status='pending_review', version=version+1,
            reviewed_at=NULL, reviewed_by=NULL, review_duration_seconds=NULL,
            review_started_at=NULL, review_notes=NULL, field_overrides='{}'::jsonb,
            sync_status='pending', sync_attempts=0, sync_last_error=NULL,
            sync_external_id=NULL, sync_idempotency_key=NULL,
            reject_count=0, last_reject_reason=NULL, last_rejected_by=NULL, last_rejected_at=NULL
            WHERE ticket_id = (SELECT id FROM ticket WHERE source_id = 9999)
        '''))
        await db.commit()
    print('done')

asyncio.run(reset())
