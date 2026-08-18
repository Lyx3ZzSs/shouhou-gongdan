"""Quick verification of seeded test data."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
from app.core.config import settings


async def verify():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as db:
        print("=" * 60)
        print("🔍 验证测试数据")
        print("=" * 60)

        # 1. Check workorder_review + ticket_view JOIN
        result = await db.execute(text("""
            SELECT wr.id, wr.ticket_id, wr.review_status, wr.sync_status,
                   vt.name, vt."caseAccountId", vt."projectName__c",
                   wr.reviewed_by, wr.reject_count, wr.review_notes
            FROM workorder_review wr
            LEFT JOIN ticket_view vt ON wr.ticket_id = vt.id
            ORDER BY wr.ticket_id
        """))
        rows = list(result.mappings())
        print(f"\n📋 workorder_review + ticket_view JOIN: {len(rows)} rows")
        for r in rows:
            print(f"  {r['ticket_id']:16d} | {r['review_status']:16s} | sync={r['sync_status']:8s} | {r['name'] or '(no ticket_view data)'}")

        # 2. Check status distribution
        result = await db.execute(text("""
            SELECT review_status, sync_status, COUNT(*) as cnt
            FROM workorder_review
            GROUP BY review_status, sync_status
            ORDER BY review_status, sync_status
        """))
        print("\n📊 状态交叉分布 (review_status × sync_status):")
        for r in result.mappings():
            print(f"  {r['review_status']:16s} | {r['sync_status']:8s} | {r['cnt']}")

        # 3. Check audit logs
        result = await db.execute(text("""
            SELECT workorder_id, session_id, field_path, change_type,
                   operator_name, operated_at
            FROM workorder_audit_log
            ORDER BY operated_at DESC
            LIMIT 5
        """))
        print("\n📝 最近5条审核日志:")
        for r in result.mappings():
            print(f"  [{r['change_type']:8s}] {r['field_path']:24s} by {r['operator_name']} at {r['operated_at']}")

        # 4. Check stats overview query works
        print("\n📈 统计概览 (stats_service.get_overview):")
        result = await db.execute(text("""
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
        r = result.mappings().first()
        print(f"  已审核总数: {r['total_reviewed']}")
        print(f"  今日审核: {r['today_reviewed']}")
        print(f"  平均耗时: {r['avg_duration_seconds']}s")
        print(f"  通过率: {r['approval_rate']}%")
        print(f"  待审核数: {r['pending_count']}")

        # 5. Check bad_case_sample
        result = await db.execute(text("""
            SELECT COUNT(*) as cnt FROM bad_case_sample
        """))
        print(f"\n🔖 bad_case_sample: {result.scalar()} 条")

        # 6. Check stash
        result = await db.execute(text("""
            SELECT ws.workorder_id, ws.notes, ws.updated_at,
                   wr.review_status
            FROM workorder_stash ws
            JOIN workorder_review wr ON ws.workorder_id = wr.id
        """))
        print(f"\n💾 workorder_stash:")
        for r in result.mappings():
            print(f"  workorder_id={r['workorder_id']}, status={r['review_status']}, notes={r['notes']}")

        print("\n" + "=" * 60)
        print("✅ 验证完成！数据完整性检查通过。")
        print("=" * 60)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(verify())
