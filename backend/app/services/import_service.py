"""工单导入服务 — 从现行 8 表工单源幂等导入审核队列。"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


async def import_workorders(db: AsyncSession) -> int:
    """幂等导入：ticket 中未在 workorder_review 的记录。

    返回导入的记录数。
    """
    duplicate = (await db.execute(text("""
        SELECT ticket_no, count(*) AS count
        FROM ticket
        GROUP BY ticket_no
        HAVING count(*) > 1
        LIMIT 1
    """))).mappings().first()
    if duplicate:
        raise ValueError(
            f"ticket_no={duplicate['ticket_no']} 存在 {duplicate['count']} 条源记录，已停止导入"
        )

    result = await db.execute(
        text("""
            INSERT INTO workorder_review (id, ticket_no, review_status, initiator, initiator_department)
            SELECT
                :prefix || gen_random_uuid()::VARCHAR(64) AS id,
                t.ticket_no,
                'pending_review',
                COALESCE(NULLIF(t."feedbackUserName_c", ''), ul.name, wu.nick_name,
                         sm.from_addr, '未知'),
                COALESCE(bec.dept_name, sm.source, ws.source, 'unknown')
            FROM ticket t
            LEFT JOIN wechat_session ws ON t.session_id = ws.id
            LEFT JOIN wechat_user wu ON ws.customer_id = wu.user_id
            LEFT JOIN user_ledger ul ON ws.customer_id = ul.user_id
            LEFT JOIN source_message sm ON t.source_id = sm.id
            LEFT JOIN beisen_employee_cache bec
                ON t."ownerId" = bec.job_number AND bec.status = 1
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
