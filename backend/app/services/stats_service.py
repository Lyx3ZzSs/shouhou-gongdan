"""审核统计服务 — 总览、按人、趋势、耗时分布、状态分布。"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class StatsService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_overview(self) -> dict:
        """总览卡片数据：已审核总数、今日审核、平均耗时、通过率、待审核数。"""
        result = await self.db.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE reviewed_at IS NOT NULL) AS total_reviewed,
                COUNT(*) FILTER (
                    WHERE reviewed_at IS NOT NULL
                      AND reviewed_at >= CURRENT_DATE
                ) AS today_reviewed,
                ROUND(AVG(review_duration_seconds)
                      FILTER (WHERE review_duration_seconds IS NOT NULL))::int
                    AS avg_duration_seconds,
                ROUND(
                    COUNT(*) FILTER (WHERE review_status = 'confirmed') * 100.0
                    / NULLIF(COUNT(*) FILTER (WHERE review_status IN ('confirmed', 'pending_review')), 0)
                )::numeric(5,1) AS approval_rate,
                COUNT(*) FILTER (WHERE review_status = 'pending_review') AS pending_count
            FROM workorder_review
            WHERE reviewed_at IS NOT NULL
               OR review_status = 'pending_review'
        """))
        row = result.mappings().first()
        return dict(row) if row else {}

    async def get_by_reviewer(
        self, from_date: str | None = None, to_date: str | None = None,
    ) -> list[dict]:
        """按审核人员统计审核量、通过/驳回数、平均耗时。"""
        params = {}
        conditions = ["reviewed_by IS NOT NULL"]
        if from_date:
            conditions.append("reviewed_at >= :from_date")
            params["from_date"] = from_date
        if to_date:
            conditions.append("reviewed_at < :to_date::date + INTERVAL '1 day'")
            params["to_date"] = to_date

        rows = await self.db.execute(text(f"""
            SELECT
                reviewed_by AS reviewer_name,
                COUNT(*) AS total_reviewed,
                COUNT(*) FILTER (WHERE review_status = 'confirmed') AS approved,
                COUNT(*) FILTER (WHERE review_status = 'pending_review') AS rejected,
                ROUND(AVG(review_duration_seconds)
                      FILTER (WHERE review_duration_seconds IS NOT NULL))::int
                    AS avg_duration_seconds
            FROM workorder_review
            WHERE {' AND '.join(conditions)}
            GROUP BY reviewed_by
            ORDER BY total_reviewed DESC
        """), params)
        return [dict(r) for r in rows.mappings()]

    async def get_trends(self, days: int = 30) -> list[dict]:
        """每日审核趋势 — 最近 N 天每天的审核量/通过/驳回数。"""
        rows = await self.db.execute(text("""
            SELECT
                d::date AS date,
                COALESCE(COUNT(w.reviewed_at), 0) AS reviewed_count,
                COALESCE(COUNT(*) FILTER (WHERE w.review_status = 'confirmed'), 0) AS approved_count,
                COALESCE(COUNT(*) FILTER (WHERE w.review_status = 'pending_review'), 0) AS rejected_count
            FROM generate_series(
                CURRENT_DATE - CAST(:days AS integer) + 1,
                CURRENT_DATE,
                '1 day'::interval
            ) AS d
            LEFT JOIN workorder_review w ON w.reviewed_at::date = d::date
            GROUP BY d::date
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
        """工单状态分布 — 待审核、审核中、已完成、已驳回。"""
        rows = await self.db.execute(text("""
            SELECT
                CASE
                    WHEN review_status = 'pending_review' THEN '待审核'
                    WHEN review_status = 'confirmed'      THEN '已通过'
                    WHEN review_status = 'returned'       THEN '已驳回'
                    ELSE review_status
                END AS status,
                COUNT(*) AS count
            FROM workorder_review
            GROUP BY 1
            ORDER BY COUNT(*) DESC
        """))
        return [dict(r) for r in rows.mappings()]
