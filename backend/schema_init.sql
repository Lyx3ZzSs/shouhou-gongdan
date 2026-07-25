-- ============================================================================
-- 售后工单审核系统 — PostgreSQL 初始化 DDL
-- 包含 ORM 模型全部字段 + 迁移 001 的变更，是最终表结构的完整快照
-- 用法: psql -h localhost -U postgres -d shouhou_gongdan -f schema_init.sql
-- ============================================================================

BEGIN;

-- 1. workorder 工单表（审核功能涉及的全部列，与 ORM 模型保持同步）
CREATE TABLE IF NOT EXISTS workorder (
    -- 主键
    id              VARCHAR(64)     PRIMARY KEY,

    -- 审核/版本追踪
    version         INTEGER         NOT NULL DEFAULT 1,
    reviewed_at     TIMESTAMP       NULL,
    reviewed_by     VARCHAR(64)     NULL,
    reject_count    INTEGER         NOT NULL DEFAULT 0,
    last_reject_reason  TEXT        NULL,
    last_rejected_by    VARCHAR(64) NULL,
    last_rejected_at    TIMESTAMP   NULL,
    review_notes    TEXT            NULL,
    sync_status     VARCHAR(16)     NOT NULL DEFAULT 'pending'
                    CHECK (sync_status IN ('pending', 'syncing', 'synced', 'failed')),
    sync_attempts   INTEGER         NOT NULL DEFAULT 0,
    sync_last_error TEXT            NULL,
    sync_idempotency_key VARCHAR(128) NULL,
    sync_external_id VARCHAR(64)    NULL,
    sync_started_at TIMESTAMPTZ     NULL,

    -- 审核计时
    review_started_at        TIMESTAMPTZ     NULL,
    review_duration_seconds  INTEGER         NULL,

    -- 只读元数据
    serial_number           VARCHAR(64)     NULL,
    status                  VARCHAR(32)     NULL,
    created_at              TIMESTAMP       NULL,
    initiator               VARCHAR(64)     NULL,
    initiator_department    VARCHAR(128)    NULL,

    -- 销售易 serviceCase API 业务字段（33 可见 + 1 hidden）
    -- Required fields
    "ownerId"               VARCHAR(64)     NULL,
    "dimDepart"             VARCHAR(128)    NULL,
    "entityType"            VARCHAR(32)     NULL DEFAULT '11010045500001',
    name                    VARCHAR(255)    NULL,
    "caseSource"            VARCHAR(32)     NULL,
    "feedbackChannel__c"    VARCHAR(32)     NULL,
    "workOrderStatus__c"    VARCHAR(32)     NULL,
    "caseDescription"       TEXT            NULL,
    "caseStatus"            VARCHAR(16)     NULL,

    -- Optional fields
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

    -- Hidden field
    "defectFlag__c"         VARCHAR(4)      NULL DEFAULT '1'
);

-- 2. workorder_audit_log 审计日志表
CREATE TABLE IF NOT EXISTS workorder_audit_log (
    id              BIGSERIAL       PRIMARY KEY,
    workorder_id    VARCHAR(64)     NOT NULL REFERENCES workorder(id) ON DELETE CASCADE,
    session_id      VARCHAR(64)     NOT NULL,
    field_path      VARCHAR(128)    NOT NULL,
    field_label     VARCHAR(64)     NOT NULL,
    old_value       TEXT            NULL,
    new_value       TEXT            NULL,
    change_type     VARCHAR(16)     NOT NULL DEFAULT 'replace'
                    CHECK (change_type IN ('replace', 'add', 'remove', 'rejected')),
    operator_id     VARCHAR(64)     NOT NULL,
    operator_name   VARCHAR(64)     NULL,
    operated_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workorder    ON workorder_audit_log (workorder_id);
CREATE INDEX IF NOT EXISTS idx_session     ON workorder_audit_log (session_id);
CREATE INDEX IF NOT EXISTS idx_operator    ON workorder_audit_log (operator_id);
CREATE INDEX IF NOT EXISTS idx_operated_at ON workorder_audit_log (operated_at);

-- 3. bad_case_sample 坏例样本表
CREATE TABLE IF NOT EXISTS bad_case_sample (
    id              BIGSERIAL       PRIMARY KEY,
    workorder_id    VARCHAR(64)     NOT NULL REFERENCES workorder(id) ON DELETE CASCADE,
    audit_log_id    BIGINT          NOT NULL REFERENCES workorder_audit_log (id),
    field_path      VARCHAR(128)    NOT NULL,
    ai_value        TEXT            NULL,
    human_value     TEXT            NULL,
    sample_status   VARCHAR(16)     NOT NULL DEFAULT 'pending'
                    CHECK (sample_status IN ('pending', 'reviewed', 'accepted', 'rejected')),
    source          VARCHAR(16)     NOT NULL DEFAULT 'review_correction',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_status    ON bad_case_sample (sample_status);
CREATE INDEX IF NOT EXISTS idx_workorder ON bad_case_sample (workorder_id);
CREATE INDEX IF NOT EXISTS idx_audit_log ON bad_case_sample (audit_log_id);

-- 4. workorder_stash 暂存表（审核进度草稿保存）
CREATE TABLE IF NOT EXISTS workorder_stash (
    id              BIGSERIAL       PRIMARY KEY,
    workorder_id    VARCHAR(64)     NOT NULL REFERENCES workorder(id) ON DELETE CASCADE,
    field_states    JSONB           NOT NULL DEFAULT '{}'::jsonb,
    notes           TEXT            NULL DEFAULT '',
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_workorder_stash_workorder_id UNIQUE (workorder_id)
);

COMMIT;
