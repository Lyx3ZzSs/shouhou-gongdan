"""审核统计服务 — 总览、按人、趋势、耗时分布、状态分布。

口径约定（驳回工单对统计可见）：
- 通过量：review_status='confirmed'，时间取 reviewed_at
- 驳回量：reject_count>0（或 last_rejected_at），时间取 last_rejected_at
- 驳回动作不写 reviewed_at/reviewed_by，因此统计中驳回与通过必须分别取数
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class StatsService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_overview(self) -> dict:
        """总览卡片数据：已审核总数、今日审核、平均耗时、最终通过率、一次通过率、待审核数。"""
        result = await self.db.execute(text("""
            SELECT
                COUNT(*) FILTER (
                    WHERE reviewed_at IS NOT NULL OR reject_count > 0
                ) AS total_reviewed,
                COUNT(*) FILTER (
                    WHERE (reviewed_at IS NOT NULL AND reviewed_at >= CURRENT_DATE)
                       OR (last_rejected_at IS NOT NULL AND last_rejected_at >= CURRENT_DATE)
                ) AS today_reviewed,
                ROUND(AVG(review_duration_seconds)
                      FILTER (WHERE review_duration_seconds IS NOT NULL))::int
                    AS avg_duration_seconds,
                -- 最终通过率：已通过 / 已评审（含被驳回返工过的）
                ROUND(
                    COUNT(*) FILTER (WHERE review_status = 'confirmed') * 100.0
                    / NULLIF(
                        COUNT(*) FILTER (WHERE reviewed_at IS NOT NULL OR reject_count > 0),
                        0)
                )::numeric(5,1) AS approval_rate,
                -- 一次通过率：无任何驳回记录即通过 / 全部通过
                ROUND(
                    COUNT(*) FILTER (
                        WHERE review_status = 'confirmed' AND reject_count = 0
                    ) * 100.0
                    / NULLIF(COUNT(*) FILTER (WHERE review_status = 'confirmed'), 0)
                )::numeric(5,1) AS one_pass_rate,
                COUNT(*) FILTER (WHERE reject_count > 0) AS total_rejected,
                COUNT(*) FILTER (WHERE review_status = 'pending_review') AS pending_count,
                COUNT(*) FILTER (WHERE review_status = 'stashed') AS stashed_count,
                COUNT(*) FILTER (WHERE sync_status IN ('failed', 'uncertain')) AS sync_failure_count,
                ROUND(
                    COUNT(*) FILTER (WHERE reject_count > 0) * 100.0
                    / NULLIF(COUNT(*) FILTER (WHERE reviewed_at IS NOT NULL OR reject_count > 0), 0)
                )::numeric(5,1) AS rejection_rate,
                ROUND(
                    (SELECT COUNT(*) FROM workorder_audit_log
                     WHERE field_path IN (
                        '/caseAccountId', '/projectName__c', '/problemResponsible__c',
                        '/feedbackUserName__c', '/feedbackUserContact__c', '/caseDescription'
                     )) * 100.0
                    / NULLIF(COUNT(*) FILTER (WHERE reviewed_at IS NOT NULL OR reject_count > 0) * 6, 0)
                )::numeric(5,1) AS ai_field_modification_rate
            FROM workorder_review
        """))
        row = result.mappings().first()
        return dict(row) if row else {}

    async def get_by_reviewer(
        self, from_date: str | None = None, to_date: str | None = None,
    ) -> list[dict]:
        """按审核人员统计审核量、通过/驳回数、平均耗时。

        通过按 reviewed_by(reviewed_at) 取数，驳回按 last_rejected_by
        (last_rejected_at) 取数，UNION 合并后按人聚合，避免驳回工单
        因无 reviewed_by 而恒为 0。
        """
        params = {}
        cond_c = ["reviewed_by IS NOT NULL"]
        cond_r = ["last_rejected_by IS NOT NULL"]
        if from_date:
            cond_c.append("reviewed_at >= :from_date")
            cond_r.append("last_rejected_at >= :from_date")
            params["from_date"] = from_date
        if to_date:
            cond_c.append("reviewed_at < :to_date::date + INTERVAL '1 day'")
            cond_r.append("last_rejected_at < :to_date::date + INTERVAL '1 day'")
            params["to_date"] = to_date

        rows = await self.db.execute(text(f"""
            WITH counts AS (
                SELECT reviewer_name, SUM(approved) AS approved, SUM(rejected) AS rejected
                FROM (
                    SELECT reviewed_by AS reviewer_name, 1 AS approved, 0 AS rejected
                    FROM workorder_review WHERE {' AND '.join(cond_c)}
                    UNION ALL
                    SELECT last_rejected_by AS reviewer_name, 0 AS approved, 1 AS rejected
                    FROM workorder_review WHERE {' AND '.join(cond_r)}
                ) u
                GROUP BY reviewer_name
            ),
            durations AS (
                SELECT reviewed_by AS reviewer_name,
                       ROUND(AVG(review_duration_seconds)
                             FILTER (WHERE review_duration_seconds IS NOT NULL))::int
                           AS avg_duration_seconds
                FROM workorder_review
                WHERE {' AND '.join(cond_c)}
                GROUP BY reviewed_by
            )
            SELECT c.reviewer_name,
                   c.approved,
                   c.rejected,
                   (c.approved + c.rejected) AS total_reviewed,
                   d.avg_duration_seconds
            FROM counts c
            LEFT JOIN durations d ON d.reviewer_name = c.reviewer_name
            ORDER BY total_reviewed DESC
        """), params)
        return [dict(r) for r in rows.mappings()]

    async def get_trends(self, days: int = 30) -> list[dict]:
        """每日审核趋势 — 最近 N 天每天的通过/驳回数。

        通过数按 reviewed_at、驳回数按 last_rejected_at 分别聚合，
        使驳回事件在趋势中可见。
        """
        rows = await self.db.execute(text("""
            SELECT
                d::date AS date,
                COALESCE(c.approved_count, 0) + COALESCE(r.rejected_count, 0) AS reviewed_count,
                COALESCE(c.approved_count, 0) AS approved_count,
                COALESCE(r.rejected_count, 0) AS rejected_count
            FROM generate_series(
                CURRENT_DATE - CAST(:days AS integer) + 1,
                CURRENT_DATE,
                '1 day'::interval
            ) AS d
            LEFT JOIN (
                SELECT reviewed_at::date AS date,
                       COUNT(*) AS approved_count
                FROM workorder_review
                WHERE reviewed_at IS NOT NULL
                GROUP BY 1
            ) c ON c.date = d::date
            LEFT JOIN (
                SELECT last_rejected_at::date AS date,
                       COUNT(*) AS rejected_count
                FROM workorder_review
                WHERE last_rejected_at IS NOT NULL
                GROUP BY 1
            ) r ON r.date = d::date
            ORDER BY d::date
        """), {"days": days})
        return [dict(r) for r in rows.mappings()]

    async def get_duration_distribution(self) -> list[dict]:
        """审核耗时分布 — 按区间统计工单数量。"""
        rows = await self.db.execute(text("""
            SELECT
                CASE
                    WHEN review_duration_seconds < 60              THEN '<1分钟'
                    WHEN review_duration_seconds < 300             THEN '1-5分钟'
                    WHEN review_duration_seconds < 900             THEN '5-15分钟'
                    WHEN review_duration_seconds < 1800            THEN '15-30分钟'
                    WHEN review_duration_seconds >= 1800           THEN '>30分钟'
                END AS range,
                COUNT(*) AS count
            FROM workorder_review
            WHERE review_duration_seconds IS NOT NULL
            GROUP BY 1
            ORDER BY MIN(review_duration_seconds)
        """))
        return [dict(r) for r in rows.mappings()]

    async def get_status_distribution(self) -> list[dict]:
        """工单状态分布 — 待审核、已通过、已驳回待返工、已暂存。"""
        rows = await self.db.execute(text("""
            SELECT
                CASE
                    WHEN review_status = 'confirmed'            THEN '已通过'
                    WHEN review_status = 'pending_review'
                         AND reject_count > 0                   THEN '已驳回待返工'
                    WHEN review_status = 'pending_review'       THEN '待审核'
                    WHEN review_status = 'stashed'              THEN '已暂存'
                    ELSE review_status
                END AS status,
                COUNT(*) AS count
            FROM workorder_review
            GROUP BY 1
            ORDER BY COUNT(*) DESC
        """))
        return [dict(r) for r in rows.mappings()]

    async def get_field_corrections(self, limit: int = 20) -> list[dict]:
        """错误字段聚合：审核中最常被修正的字段（audit_log.field_label）。"""
        rows = await self.db.execute(text("""
            SELECT
                field_label,
                field_path,
                COUNT(*) AS correction_count
            FROM workorder_audit_log
            WHERE change_type IN ('replace', 'add', 'remove')
            GROUP BY field_label, field_path
            ORDER BY correction_count DESC
            LIMIT :limit
        """), {"limit": limit})
        return [dict(r) for r in rows.mappings()]

    async def get_efficiency(self, weeks: int = 12) -> list[dict]:
        """售后效率趋势：按确认周聚合 一次通过率 / 平均返工 / 平均修正 / 同步接受率。

        口径：只统计已确认工单（reviewed_at IS NOT NULL），按确认周分组；
        reject_count 与 audit_log 在确认时已固化，可做周间横向对比。
        sync_acceptance_rate 依赖销售易同步启用（XIAOSHOUYI_BASE_URL 非空）。
        """
        rows = await self.db.execute(text("""
            WITH corrections AS (
                SELECT workorder_id, COUNT(*) AS cnt
                FROM workorder_audit_log
                WHERE change_type IN ('replace', 'add', 'remove')
                GROUP BY workorder_id
            )
            SELECT
                date_trunc('week', w.reviewed_at)::date AS week,
                COUNT(*) AS confirmed_count,
                ROUND(
                    COUNT(*) FILTER (WHERE w.reject_count = 0) * 100.0
                    / NULLIF(COUNT(*), 0)
                )::numeric(5,1) AS one_pass_rate,
                ROUND(AVG(w.reject_count)::numeric, 2) AS avg_reject_count,
                ROUND(AVG(COALESCE(c.cnt, 0))::numeric, 2) AS avg_corrections,
                ROUND(
                    COUNT(*) FILTER (WHERE w.sync_status = 'synced') * 100.0
                    / NULLIF(COUNT(*), 0)
                )::numeric(5,1) AS sync_acceptance_rate
            FROM workorder_review w
            LEFT JOIN corrections c ON c.workorder_id = w.id
            WHERE w.reviewed_at IS NOT NULL
              AND w.reviewed_at >= CURRENT_DATE - CAST(:weeks AS integer) * INTERVAL '1 week'
            GROUP BY date_trunc('week', w.reviewed_at)
            ORDER BY week
        """), {"weeks": weeks})
        return [dict(r) for r in rows.mappings()]
