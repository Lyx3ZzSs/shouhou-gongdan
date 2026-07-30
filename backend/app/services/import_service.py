"""工单导入服务 — 从 ticket_source.ticket 幂等导入到 workorder_review。"""

import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


async def import_workorders(db: AsyncSession) -> int:
    """幂等导入：ticket_source.ticket 中未在 workorder_review 的记录。

    返回导入的记录数。
    """
    result = await db.execute(
        text("""
            INSERT INTO workorder_review (id, ticket_no, review_status, initiator, initiator_department)
            SELECT
                :prefix || gen_random_uuid()::VARCHAR(64) AS id,
                t.ticket_no,
                'pending_review',
                COALESCE(wu.nick_name, '未知'),
                COALESCE(sm.source, 'unknown')
            FROM ticket_source.ticket t
            LEFT JOIN ticket_source.source_message sm ON t.source_id = sm.id
            LEFT JOIN ticket_source.wechat_user wu ON sm.user_id = wu.user_id
            WHERE NOT EXISTS (
                SELECT 1 FROM workorder_review wr WHERE wr.ticket_no = t.ticket_no
            )
            RETURNING id
        """),
        {"prefix": "wo-"},
    )
    await db.commit()
    count = result.rowcount
    if count > 0:
        logger.info("导入 %d 条工单到 workorder_review", count)
    return count
