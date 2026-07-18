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
        sync_status     VARCHAR(16)     NOT NULL DEFAULT 'pending',
        serial_number           VARCHAR(64)     NULL,
        status                  VARCHAR(32)     NULL,
        created_at              TIMESTAMP       NULL,
        initiator               VARCHAR(64)     NULL,
        initiator_department    VARCHAR(128)    NULL,
        station_name            VARCHAR(255)    NULL,
        dispatch_name           VARCHAR(255)    NULL,
        project_code            VARCHAR(64)     NULL,
        project_name            VARCHAR(255)    NULL,
        project_province        VARCHAR(64)     NULL,
        customer_name           VARCHAR(255)    NULL,
        problem_description     TEXT            NULL,
        feedback_channel        VARCHAR(64)     NULL,
        product_line            VARCHAR(64)     NULL,
        product_category        VARCHAR(64)     NULL,
        product_type            VARCHAR(64)     NULL,
        customer_level          VARCHAR(32)     NULL,
        problem_category_l1     VARCHAR(64)     NULL,
        problem_category_l2     VARCHAR(64)     NULL,
        problem_category_l3     VARCHAR(64)     NULL,
        order_type              VARCHAR(32)     NULL,
        problem_type            VARCHAR(64)     NULL,
        fault_category          VARCHAR(64)     NULL,
        fault_detail            TEXT            NULL,
        responsible_person      VARCHAR(64)     NULL,
        responsible_department  VARCHAR(128)    NULL,
        primary_department      VARCHAR(128)    NULL,
        after_sales_person      VARCHAR(64)     NULL,
        transferred_person      VARCHAR(64)     NULL,
        transferred_department  VARCHAR(128)    NULL,
        order_level             VARCHAR(32)     NULL,
        fault_level             VARCHAR(32)     NULL,
        onsite_level            VARCHAR(32)     NULL,
        required_solve_time     VARCHAR(64)     NULL
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
        operated_at     TIMESTAMP       NOT NULL DEFAULT NOW()
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
        source          VARCHAR(16)     NOT NULL DEFAULT 'review_correction',
        created_at      TIMESTAMP       NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_badcase_status    ON bad_case_sample (sample_status)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_badcase_workorder ON bad_case_sample (workorder_id)
    """,
]


async def main():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        for stmt in STATEMENTS:
            print(f"→ {stmt.strip().splitlines()[0].strip()}")
            await conn.execute(sa_text(stmt))

    print("\n✅ 3 张表 + 6 个索引创建完成")
    print("下一步: alembic stamp head")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
