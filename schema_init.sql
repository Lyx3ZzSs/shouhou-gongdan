-- ============================================================================
-- 售后工单审核系统 — PostgreSQL 初始化 DDL
--
-- 与 ORM 模型严格同步（backend/app/models/）：
--   workorder_review  → WorkOrderReview
--   workorder_audit_log → WorkOrderAuditLog
--   bad_case_sample   → BadCaseSample
--   workorder_stash   → WorkOrderStash
--   v_ticket          → VTicket（视图，依赖外部表）
--
-- 用法: psql -h localhost -U postgres -d shouhou_gongdan -f schema_init.sql
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. workorder_review — 审核元数据表
-- ============================================================================
CREATE TABLE IF NOT EXISTS workorder_review (
    -- 主键（与 ticket_source.ticket.id 对应）
    id                      VARCHAR(64)     PRIMARY KEY,

    -- 关联键（关联 ticket_source.ticket.ticket_no，非 DB FK）
    ticket_no               VARCHAR(100)    NOT NULL UNIQUE,

    -- 乐观锁版本号
    version                 INTEGER         NOT NULL DEFAULT 1,

    -- 审核状态: pending_review | reviewing | confirmed | returned | stashed
    review_status           VARCHAR(32)     NOT NULL DEFAULT 'pending_review',

    -- 审核结果
    reviewed_at             TIMESTAMP       NULL,
    reviewed_by             VARCHAR(64)     NULL,
    reject_count            INTEGER         NOT NULL DEFAULT 0,
    last_reject_reason      TEXT            NULL,
    last_rejected_by        VARCHAR(64)     NULL,
    last_rejected_at        TIMESTAMP       NULL,
    review_notes            TEXT            NULL,

    -- 审核计时
    review_started_at       TIMESTAMPTZ     NULL,
    review_duration_seconds INTEGER         NULL,

    -- 审核编辑（JSONB，覆盖 v_ticket 字段值的增量修改）
    field_overrides         JSONB           NOT NULL DEFAULT '{}'::jsonb,

    -- 同步至销售易
    sync_status             VARCHAR(16)     NOT NULL DEFAULT 'pending'
                            CHECK (sync_status IN ('pending', 'syncing', 'synced', 'failed')),
    sync_attempts           INTEGER         NOT NULL DEFAULT 0,
    sync_last_error         TEXT            NULL,
    sync_idempotency_key    VARCHAR(128)    NULL,
    sync_external_id        VARCHAR(64)     NULL,
    sync_started_at         TIMESTAMPTZ     NULL,

    -- 发起人信息（导入时从 ticket_source 冗余存储）
    initiator               VARCHAR(64)     NULL,
    initiator_department    VARCHAR(128)    NULL,

    -- 时间戳
    created_at              TIMESTAMP       NOT NULL,
    updated_at              TIMESTAMP       NOT NULL
);

-- ============================================================================
-- 2. workorder_audit_log — 审核审计日志表
-- ============================================================================
CREATE TABLE IF NOT EXISTS workorder_audit_log (
    id              BIGSERIAL       PRIMARY KEY,
    workorder_id    VARCHAR(64)     NOT NULL,
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
CREATE INDEX IF NOT EXISTS idx_session      ON workorder_audit_log (session_id);
CREATE INDEX IF NOT EXISTS idx_operator     ON workorder_audit_log (operator_id);
CREATE INDEX IF NOT EXISTS idx_operated_at  ON workorder_audit_log (operated_at);

-- ============================================================================
-- 3. bad_case_sample — AI 审核坏例样本表
-- ============================================================================
CREATE TABLE IF NOT EXISTS bad_case_sample (
    id              BIGSERIAL       PRIMARY KEY,
    workorder_id    VARCHAR(64)     NOT NULL,
    audit_log_id    BIGINT          NOT NULL REFERENCES workorder_audit_log (id),
    field_path      VARCHAR(128)    NOT NULL,
    ai_value        TEXT            NULL,
    human_value     TEXT            NULL,
    sample_status   VARCHAR(16)     NOT NULL DEFAULT 'pending'
                    CHECK (sample_status IN ('pending', 'reviewed', 'accepted', 'rejected')),
    source          VARCHAR(32)     NOT NULL DEFAULT 'review_correction',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bcs_status    ON bad_case_sample (sample_status);
CREATE INDEX IF NOT EXISTS idx_bcs_workorder ON bad_case_sample (workorder_id);
CREATE INDEX IF NOT EXISTS idx_bcs_audit_log ON bad_case_sample (audit_log_id);

-- ============================================================================
-- 4. workorder_stash — 审核进度暂存表
-- ============================================================================
CREATE TABLE IF NOT EXISTS workorder_stash (
    id              BIGSERIAL       PRIMARY KEY,
    workorder_id    VARCHAR(64)     NOT NULL UNIQUE,
    field_states    JSONB           NOT NULL DEFAULT '{}'::jsonb,
    notes           TEXT            NULL DEFAULT '',
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP       NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 5. v_ticket — 工单业务数据视图（只读）
--
-- ⚠️ 外部依赖：此视图依赖以下外部表，需确保它们在数据库中已存在：
--   - ticket_source.ticket   (ticket_no, 及所有销售易 __c 业务字段)
--   - project_info            (caseAccountId, custLevel1__c, projectName__c, ...)
--
-- 视图结构对照 ORM 模型 VTicket（backend/app/models/ticket.py），
-- 提供 ticket_source.ticket LEFT JOIN project_info 的统一查询入口。
-- 审核模块所有业务字段读取均通过此视图。
-- ============================================================================

-- 以下为视图预期结构（列名与 ORM 模型一致），实际创建时请根据
-- ticket_source.ticket 和 project_info 的实际列名调整 SELECT 映射。
--
-- CREATE OR REPLACE VIEW v_ticket AS
-- SELECT
--     t.id,
--     t.ticket_no,
--     t."ownerId",
--     t."dimDepart",
--     t."entityType",
--     t."name",
--     t."caseSource",
--     t."feedbackChannel__c",
--     t."workOrderStatus__c",
--     t."caseDescription",
--     t."caseStatus",
--     t."problemLevel__c",
--     t."feedbackUserContact__c",
--     t."feedbackUserName__c",
--     t."problemResponsible__c",
--     t."problemDept__c",
--     t."problemType1__c",
--     t."problemType2__c",
--     t."problemType3__c",
--     t."feedbackCount__c",
--     t."needCallBack__c",
--     t."isHandled__c",
--     t."needOnSite__c",
--     t."remark__c",
--     t."planFeedbackTime__c",
--     t."requireSolveTime__c",
--     t."defectFlag__c",
--     p."caseAccountId",
--     p."custLevel1__c",
--     p."projectName__c",
--     p."projectProvince__c",
--     p."bigCustShortName__c",
--     p."serviceCycleStart__c",
--     p."serviceCycleEnd__c",
--     p."isOfflineApply__c",
--     p."isOverdueService__c"
-- FROM ticket_source.ticket t
-- LEFT JOIN project_info p ON t.project_id = p.id;

COMMIT;
