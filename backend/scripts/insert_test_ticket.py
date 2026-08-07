"""
插入单条测试工单数据 — 清空旧数据后导入用户指定的测试记录。

用法:
  cd backend && .venv/bin/python scripts/insert_test_ticket.py
"""

import asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
from app.core.config import settings

# ── 用户提供的测试数据（已映射为正确的 camelCase 列名）────────────────
TICKET_DATA = {
    # ticket 表字段
    "ticket_no": "SRV-2026-0099",
    "ownerId": "101634",
    "dimDepart": "sprixin",
    "entityType": "11010045500001",
    "name": "售后单",
    "caseSource": "6",
    "feedbackChannel__c": "6",
    "workOrderStatus__c": "3",
    "caseDescription": "客户发送了多个售后单，涉及陕西讨素海光伏电站、山西樊安光伏电站、新疆大河沿风电场、广东茭一光伏电站、新疆丝路网能巴楚光伏一电站、宁夏太阳山第四风电场、湖北通力光储电站光伏电站、重庆丰都莲花山风电场、重庆咸宜光伏电站、湖南秀甲风电场、河南岭礼风电场、山西长治武乡佑福光伏电站、山西海发风电场、上海华港二期风电场等场站的系统问题，要求处理这些售后单。",
    "caseStatus": "2",
    "problemLevel__c": "2",
    "feedbackUserContact__c": "10101333333@qq.com",
    "feedbackUserName__c": "向逸辉",
    "problemResponsible__c": "100658",
    "problemDept__c": "576825",
    "problemType1__c": "1",
    "problemType2__c": "1",
    "problemType3__c": "89",
    "feedbackCount__c": "1",
    "needCallBack__c": "1",
    "isHandled__c": "2",
    "needOnSite__c": "2",
    "remark__c": "1",
    "planFeedbackTime__c": "1785837988",
    "requireSolveTime__c": "1785837988",
    "defectFlag__c": "1",
    "caseAccountId": "CZ1000001",
    # project_info 字段
    "projectName__c": "XSJH20260528003",
    "projectProvince__c": "北京市",
    "bigCustShortName__c": "",
    "serviceCycleStart__c": "178497500",
    "serviceCycleEnd__c": "178497500",
    "isOfflineApply__c": "2",  # false → "2"(否)
    "isOverdueService__c": "2",  # false → "2"(否)
    "custLevel1__c": "",
    # 发起人
    "initiator": "向逸辉",
    "initiator_dept": "售后部",
}

# ── 清理语句 ──
CLEANUP_STATEMENTS = [
    "DROP VIEW IF EXISTS v_ticket CASCADE",
    "DROP TABLE IF EXISTS ticket_source.ticket CASCADE",
    "DROP TABLE IF EXISTS ticket_source.source_message CASCADE",
    "DROP TABLE IF EXISTS ticket_source.wechat_user CASCADE",
    "DROP TABLE IF EXISTS ticket_source.project_info CASCADE",
    "DELETE FROM bad_case_sample",
    "DELETE FROM workorder_audit_log",
    "DELETE FROM workorder_stash",
    "DELETE FROM workorder_review",
]


async def main():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with async_session() as db:
            # ── 1. 清空所有旧数据 ──
            print("🧹 清空旧数据...")
            for stmt in CLEANUP_STATEMENTS:
                await db.execute(text(stmt))
            await db.commit()
            print("  ✅ 清理完成")

            # ── 2. 重建 schema 和表 ──
            print("📦 重建 ticket_source schema 和表...")
            await db.execute(text("CREATE SCHEMA IF NOT EXISTS ticket_source"))

            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS ticket_source.wechat_user (
                    user_id BIGINT PRIMARY KEY,
                    nick_name VARCHAR(64) NOT NULL,
                    source VARCHAR(64) NOT NULL
                )
            """))
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS ticket_source.source_message (
                    id BIGINT PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES ticket_source.wechat_user(user_id),
                    source VARCHAR(64) NOT NULL,
                    content TEXT
                )
            """))
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS ticket_source.ticket (
                    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                    ticket_no VARCHAR(100) NOT NULL UNIQUE,
                    source_id BIGINT REFERENCES ticket_source.source_message(id),
                    "ownerId" VARCHAR(64),
                    "dimDepart" VARCHAR(128),
                    "entityType" VARCHAR(32) DEFAULT '11010045500001',
                    name VARCHAR(255),
                    "caseSource" VARCHAR(32),
                    "feedbackChannel__c" VARCHAR(32),
                    "workOrderStatus__c" VARCHAR(32),
                    "caseDescription" TEXT,
                    "caseStatus" VARCHAR(16),
                    "caseAccountId" VARCHAR(64),
                    "custLevel1__c" VARCHAR(32),
                    "projectName__c" VARCHAR(255),
                    "projectProvince__c" VARCHAR(64),
                    "bigCustShortName__c" VARCHAR(128),
                    "serviceCycleStart__c" VARCHAR(32),
                    "serviceCycleEnd__c" VARCHAR(32),
                    "isOfflineApply__c" VARCHAR(4),
                    "isOverdueService__c" VARCHAR(4),
                    "problemLevel__c" VARCHAR(32),
                    "problemType1__c" VARCHAR(32),
                    "problemType2__c" VARCHAR(64),
                    "problemType3__c" VARCHAR(64),
                    "feedbackCount__c" VARCHAR(16),
                    "problemResponsible__c" VARCHAR(64),
                    "problemDept__c" VARCHAR(128),
                    "feedbackUserName__c" VARCHAR(64),
                    "feedbackUserContact__c" VARCHAR(200),
                    "needCallBack__c" VARCHAR(4),
                    "isHandled__c" VARCHAR(4),
                    "needOnSite__c" VARCHAR(4),
                    "remark__c" TEXT,
                    "relatedAttachment__c" VARCHAR(255),
                    "planFeedbackTime__c" VARCHAR(32),
                    "requireSolveTime__c" VARCHAR(32),
                    "defectFlag__c" VARCHAR(4) DEFAULT '1'
                )
            """))
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS ticket_source.project_info (
                    "caseAccountId" VARCHAR(64) PRIMARY KEY,
                    "custLevel1__c" VARCHAR(32),
                    "projectName__c" VARCHAR(255),
                    "projectProvince__c" VARCHAR(64),
                    "bigCustShortName__c" VARCHAR(128),
                    "serviceCycleStart__c" VARCHAR(32),
                    "serviceCycleEnd__c" VARCHAR(32),
                    "isOfflineApply__c" VARCHAR(4),
                    "isOverdueService__c" VARCHAR(4)
                )
            """))
            await db.commit()
            print("  ✅ 表结构就绪")

            # ── 3. 重建 v_ticket 视图 ──
            print("👁  重建 v_ticket 视图...")
            await db.execute(text("DROP VIEW IF EXISTS v_ticket CASCADE"))
            await db.execute(text("""
                CREATE VIEW v_ticket AS
                SELECT
                    t.id, t.ticket_no,
                    t."ownerId", t."dimDepart", t."entityType", t.name,
                    t."caseSource", t."feedbackChannel__c", t."workOrderStatus__c",
                    t."caseDescription", t."caseStatus",
                    t."problemLevel__c", t."problemType1__c", t."problemType2__c", t."problemType3__c",
                    t."feedbackCount__c", t."problemResponsible__c", t."problemDept__c",
                    t."feedbackUserName__c", t."feedbackUserContact__c",
                    t."needCallBack__c", t."isHandled__c", t."needOnSite__c",
                    t."remark__c", t."relatedAttachment__c",
                    t."planFeedbackTime__c", t."requireSolveTime__c", t."defectFlag__c",
                    pi."caseAccountId", pi."custLevel1__c", pi."projectName__c",
                    pi."projectProvince__c", pi."bigCustShortName__c",
                    pi."serviceCycleStart__c", pi."serviceCycleEnd__c",
                    pi."isOfflineApply__c", pi."isOverdueService__c"
                FROM ticket_source.ticket t
                LEFT JOIN ticket_source.project_info pi ON t."caseAccountId" = pi."caseAccountId"
            """))
            await db.commit()
            print("  ✅ v_ticket 视图就绪")

            # ── 4. 插入辅助数据 ──
            print("🌱 插入辅助数据...")
            # wechat_user
            await db.execute(
                text("INSERT INTO ticket_source.wechat_user (user_id, nick_name, source) VALUES (:uid, :nick, :source) ON CONFLICT DO NOTHING"),
                {"uid": 9999, "nick": TICKET_DATA["initiator"], "source": TICKET_DATA["initiator_dept"]},
            )
            # source_message
            await db.execute(
                text("INSERT INTO ticket_source.source_message (id, user_id, source, content) VALUES (:id, :uid, :source, :content) ON CONFLICT DO NOTHING"),
                {"id": 9999, "uid": 9999, "source": TICKET_DATA["feedbackChannel__c"], "content": TICKET_DATA["caseDescription"][:200]},
            )
            # project_info
            await db.execute(
                text("""
                    INSERT INTO ticket_source.project_info (
                        "caseAccountId", "custLevel1__c", "projectName__c",
                        "projectProvince__c", "bigCustShortName__c",
                        "serviceCycleStart__c", "serviceCycleEnd__c",
                        "isOfflineApply__c", "isOverdueService__c"
                    ) VALUES (:aid, :cl, :pn, :pp, :bc, :scs, :sce, :ioa, :ios)
                    ON CONFLICT ("caseAccountId") DO NOTHING
                """),
                {
                    "aid": TICKET_DATA["caseAccountId"],
                    "cl": TICKET_DATA["custLevel1__c"],
                    "pn": TICKET_DATA["projectName__c"],
                    "pp": TICKET_DATA["projectProvince__c"],
                    "bc": TICKET_DATA["bigCustShortName__c"],
                    "scs": TICKET_DATA["serviceCycleStart__c"],
                    "sce": TICKET_DATA["serviceCycleEnd__c"],
                    "ioa": TICKET_DATA["isOfflineApply__c"],
                    "ios": TICKET_DATA["isOverdueService__c"],
                },
            )
            # ticket
            await db.execute(
                text("""
                    INSERT INTO ticket_source.ticket (
                        ticket_no, source_id,
                        "ownerId", "dimDepart", "entityType", name,
                        "caseSource", "feedbackChannel__c", "workOrderStatus__c",
                        "caseDescription", "caseStatus",
                        "problemLevel__c", "problemType1__c", "problemType2__c", "problemType3__c",
                        "problemResponsible__c", "problemDept__c",
                        "feedbackUserName__c", "feedbackUserContact__c",
                        "feedbackCount__c", "needCallBack__c", "isHandled__c", "needOnSite__c",
                        "remark__c", "planFeedbackTime__c", "requireSolveTime__c", "defectFlag__c",
                        "caseAccountId"
                    ) VALUES (
                        :ticket_no, :source_id,
                        :ownerId, :dimDepart, :entityType, :name,
                        :caseSource, :feedbackChannel__c, :workOrderStatus__c,
                        :caseDescription, :caseStatus,
                        :problemLevel__c, :problemType1__c, :problemType2__c, :problemType3__c,
                        :problemResponsible__c, :problemDept__c,
                        :feedbackUserName__c, :feedbackUserContact__c,
                        :feedbackCount__c, :needCallBack__c, :isHandled__c, :needOnSite__c,
                        :remark__c, :planFeedbackTime__c, :requireSolveTime__c, :defectFlag__c,
                        :caseAccountId
                    )
                """),
                {
                    "ticket_no": TICKET_DATA["ticket_no"],
                    "source_id": 9999,
                    "ownerId": TICKET_DATA["ownerId"],
                    "dimDepart": TICKET_DATA["dimDepart"],
                    "entityType": TICKET_DATA["entityType"],
                    "name": TICKET_DATA["name"],
                    "caseSource": TICKET_DATA["caseSource"],
                    "feedbackChannel__c": TICKET_DATA["feedbackChannel__c"],
                    "workOrderStatus__c": TICKET_DATA["workOrderStatus__c"],
                    "caseDescription": TICKET_DATA["caseDescription"],
                    "caseStatus": TICKET_DATA["caseStatus"],
                    "problemLevel__c": TICKET_DATA["problemLevel__c"],
                    "problemType1__c": TICKET_DATA["problemType1__c"],
                    "problemType2__c": TICKET_DATA["problemType2__c"],
                    "problemType3__c": TICKET_DATA["problemType3__c"],
                    "problemResponsible__c": TICKET_DATA["problemResponsible__c"],
                    "problemDept__c": TICKET_DATA["problemDept__c"],
                    "feedbackUserName__c": TICKET_DATA["feedbackUserName__c"],
                    "feedbackUserContact__c": TICKET_DATA["feedbackUserContact__c"],
                    "feedbackCount__c": TICKET_DATA["feedbackCount__c"],
                    "needCallBack__c": TICKET_DATA["needCallBack__c"],
                    "isHandled__c": TICKET_DATA["isHandled__c"],
                    "needOnSite__c": TICKET_DATA["needOnSite__c"],
                    "remark__c": TICKET_DATA["remark__c"],
                    "planFeedbackTime__c": TICKET_DATA["planFeedbackTime__c"],
                    "requireSolveTime__c": TICKET_DATA["requireSolveTime__c"],
                    "defectFlag__c": TICKET_DATA["defectFlag__c"],
                    "caseAccountId": TICKET_DATA["caseAccountId"],
                },
            )
            await db.commit()
            print("  ✅ 测试数据插入完成")

            # ── 5. 导入到 workorder_review ──
            print("📥 导入到 workorder_review...")
            from app.services.import_service import import_workorders
            count = await import_workorders(db)
            print(f"  ✅ 导入 {count} 条记录")

        # ── 6. 验证 ──
        print("\n🔍 验证数据...")
        async with async_session() as db:
            # v_ticket 查询
            r = await db.execute(
                text("SELECT ticket_no, name, \"caseAccountId\", \"projectName__c\" FROM v_ticket")
            )
            rows = r.mappings().all()
            print(f"  v_ticket 记录数: {len(rows)}")
            for row in rows:
                print(f"    {row['ticket_no']} | {row['name']} | {row['caseAccountId']} | {row['projectName__c']}")

            # workorder_review 查询
            r = await db.execute(
                text("SELECT id, ticket_no, review_status, sync_status FROM workorder_review")
            )
            rows = r.mappings().all()
            print(f"  workorder_review 记录数: {len(rows)}")
            for row in rows:
                print(f"    {row['id']} | {row['ticket_no']} | {row['review_status']} | {row['sync_status']}")

        print("\n✅ 完成！")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
