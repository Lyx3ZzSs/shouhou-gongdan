"""初始化 PostgreSQL 表结构。

用法: cd backend && source .venv/bin/activate && python init_pg.py
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text as sa_text
from app.core.config import settings

STATEMENTS = [
    # 1. workorder 工单表
    """
    CREATE TABLE IF NOT EXISTS workorder (
        id              VARCHAR(64)     PRIMARY KEY,
        version         INTEGER         NOT NULL DEFAULT 1,
        reviewed_at     TIMESTAMP       NULL,
        reviewed_by     VARCHAR(64)     NULL,
        reject_count    INTEGER         NOT NULL DEFAULT 0,
        last_reject_reason  TEXT        NULL,
        last_rejected_by    VARCHAR(64) NULL,
        last_rejected_at    TIMESTAMP   NULL,
        review_notes    TEXT            NULL,
        sync_status     VARCHAR(16)     NOT NULL DEFAULT 'pending',
        sync_attempts   INTEGER         NOT NULL DEFAULT 0,
        sync_last_error TEXT            NULL,
        sync_idempotency_key VARCHAR(128) NULL,
        sync_external_id VARCHAR(64)    NULL,
        serial_number           VARCHAR(64)     NULL,
        status                  VARCHAR(32)     NULL,
        created_at              TIMESTAMP       NULL,
        initiator               VARCHAR(64)     NULL,
        initiator_department    VARCHAR(128)    NULL,
        -- 销售易 serviceCase API 业务字段（含大写字母的列名必须加双引号）
        "ownerId"               VARCHAR(64)     NULL,
        "dimDepart"             VARCHAR(128)    NULL,
        "entityType"            VARCHAR(32)     NULL DEFAULT '11010045500001',
        name                    VARCHAR(255)    NULL,
        "caseSource"            VARCHAR(32)     NULL,
        "feedbackChannel__c"    VARCHAR(32)     NULL,
        "workOrderStatus__c"    VARCHAR(32)     NULL,
        "caseDescription"       TEXT            NULL,
        "caseStatus"            VARCHAR(16)     NULL,
        "caseAccountId"         VARCHAR(64)     NULL,
        "custLevel1__c"         VARCHAR(32)     NULL,
        "projectName__c"        VARCHAR(255)    NULL,
        "projectProvince__c"    VARCHAR(64)     NULL,
        "bigCustShortName__c"   VARCHAR(128)    NULL,
        "serviceCycleStart__c"  VARCHAR(32)     NULL,
        "serviceCycleEnd__c"    VARCHAR(32)     NULL,
        "isOfflineApply__c"     VARCHAR(4)      NULL,
        "isOverdueService__c"   VARCHAR(4)      NULL,
        "problemLevel__c"       VARCHAR(32)     NULL,
        "problemType1__c"       VARCHAR(32)     NULL,
        "problemType2__c"       VARCHAR(64)     NULL,
        "problemType3__c"       VARCHAR(64)     NULL,
        "feedbackCount__c"      VARCHAR(16)     NULL,
        "problemResponsible__c" VARCHAR(64)     NULL,
        "problemDept__c"        VARCHAR(128)    NULL,
        "feedbackUserName__c"   VARCHAR(64)     NULL,
        "feedbackUserContact__c" VARCHAR(16)    NULL,
        "needCallBack__c"       VARCHAR(4)      NULL,
        "isHandled__c"          VARCHAR(4)      NULL,
        "needOnSite__c"         VARCHAR(4)      NULL,
        remark__c               TEXT            NULL,
        "relatedAttachment__c"  VARCHAR(255)    NULL,
        "planFeedbackTime__c"   VARCHAR(32)     NULL,
        "requireSolveTime__c"   VARCHAR(32)     NULL,
        "defectFlag__c"         VARCHAR(4)      NULL DEFAULT '1'
    )
    """,
    # 2. workorder_audit_log 审计日志表
    """
    CREATE TABLE IF NOT EXISTS workorder_audit_log (
        id              BIGSERIAL       PRIMARY KEY,
        workorder_id    VARCHAR(64)     NOT NULL,
        session_id      VARCHAR(64)     NOT NULL,
        field_path      VARCHAR(128)    NOT NULL,
        field_label     VARCHAR(64)     NOT NULL,
        old_value       TEXT            NULL,
        new_value       TEXT            NULL,
        change_type     VARCHAR(16)     NOT NULL DEFAULT 'replace',
        operator_id     VARCHAR(64)     NOT NULL,
        operator_name   VARCHAR(64)     NULL,
        operated_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_workorder    ON workorder_audit_log (workorder_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_session     ON workorder_audit_log (session_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_operator    ON workorder_audit_log (operator_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_operated_at ON workorder_audit_log (operated_at)
    """,
    # 3. bad_case_sample 坏例样本表
    """
    CREATE TABLE IF NOT EXISTS bad_case_sample (
        id              BIGSERIAL       PRIMARY KEY,
        workorder_id    VARCHAR(64)     NOT NULL,
        audit_log_id    BIGINT          NOT NULL REFERENCES workorder_audit_log (id),
        field_path      VARCHAR(128)    NOT NULL,
        ai_value        TEXT            NULL,
        human_value     TEXT            NULL,
        sample_status   VARCHAR(16)     NOT NULL DEFAULT 'pending',
        source          VARCHAR(32)     NOT NULL DEFAULT 'review_correction',
        created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_status    ON bad_case_sample (sample_status)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_workorder ON bad_case_sample (workorder_id)
    """,
    # 4. workorder_stash 暂存表（审核进度草稿保存）
    """
    CREATE TABLE IF NOT EXISTS workorder_stash (
        id              BIGSERIAL       PRIMARY KEY,
        workorder_id    VARCHAR(64)     NOT NULL,
        field_states    JSONB           NOT NULL DEFAULT '{}'::jsonb,
        notes           TEXT            NULL DEFAULT '',
        created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_workorder_stash_workorder_id UNIQUE (workorder_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_workorder_stash_workorder_id ON workorder_stash (workorder_id)
    """,
]


async def main():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        for stmt in STATEMENTS:
            print(f"→ {stmt.strip().splitlines()[0].strip()}")
            await conn.execute(sa_text(stmt))

    print("\n✅ 4 张表 + 7 个索引创建完成")
    print("下一步: alembic stamp head")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
