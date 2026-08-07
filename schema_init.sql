-- ============================================================================
-- 售后工单审核系统 — PostgreSQL 初始化 DDL
--
-- 与 ORM 模型严格同步（backend/app/models/），并从实际数据库导出验证。
-- 覆盖 public 和 ticket_source 两个 schema。
--
-- 用法: psql -h localhost -U postgres -d shouhou_gongdan -f schema_init.sql
-- ============================================================================

BEGIN;

-- ============================================================================
-- Schema: ticket_source — 工单原始数据（外部系统/source of truth）
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS ticket_source;

-- ----------------------------------------------------------------------------
-- ticket_source.wechat_user — 微信用户
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ticket_source.wechat_user (
    user_id     BIGINT          NOT NULL,
    nick_name   VARCHAR(64)     NOT NULL,
    source      VARCHAR(64)     NOT NULL,
    CONSTRAINT wechat_user_pkey PRIMARY KEY (user_id)
);

-- ----------------------------------------------------------------------------
-- ticket_source.source_message — 消息来源
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ticket_source.source_message (
    id          BIGINT          NOT NULL,
    user_id     BIGINT          NOT NULL REFERENCES ticket_source.wechat_user (user_id),
    source      VARCHAR(64)     NOT NULL,
    content     TEXT            NULL,
    CONSTRAINT source_message_pkey PRIMARY KEY (id)
);

-- ----------------------------------------------------------------------------
-- ticket_source.project_info — 项目信息
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ticket_source.project_info (
    "caseAccountId"         VARCHAR(64)     NOT NULL,
    "custLevel1__c"         VARCHAR(32)     NULL,
    "projectName__c"        VARCHAR(255)    NULL,
    "projectProvince__c"    VARCHAR(64)     NULL,
    "bigCustShortName__c"   VARCHAR(128)    NULL,
    "serviceCycleStart__c"  VARCHAR(32)     NULL,
    "serviceCycleEnd__c"    VARCHAR(32)     NULL,
    "isOfflineApply__c"     VARCHAR(4)      NULL,
    "isOverdueService__c"   VARCHAR(4)      NULL,
    CONSTRAINT project_info_pkey PRIMARY KEY ("caseAccountId")
);

-- ----------------------------------------------------------------------------
-- ticket_source.ticket — 工单业务数据（销售易 serviceCase API 字段）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ticket_source.ticket (
    id                      BIGINT          NOT NULL,
    ticket_no               VARCHAR(100)    NOT NULL,
    source_id               BIGINT          NULL REFERENCES ticket_source.source_message (id),

    -- 销售易 required fields
    "ownerId"               VARCHAR(64)     NULL,
    "dimDepart"             VARCHAR(128)    NULL,
    "entityType"            VARCHAR(32)     NULL DEFAULT '11010045500001',
    name                    VARCHAR(255)    NULL,
    "caseSource"            VARCHAR(32)     NULL,
    "feedbackChannel__c"    VARCHAR(32)     NULL,
    "workOrderStatus__c"    VARCHAR(32)     NULL,
    "caseDescription"       TEXT            NULL,
    "caseStatus"            VARCHAR(16)     NULL,

    -- 销售易 optional fields
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

    -- 销售易 hidden field
    "defectFlag__c"         VARCHAR(4)      NULL DEFAULT '1',

    CONSTRAINT ticket_pkey PRIMARY KEY (id),
    CONSTRAINT ticket_ticket_no_key UNIQUE (ticket_no)
);

-- ----------------------------------------------------------------------------
-- ticket_source.ticket_attachment — 工单附件
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ticket_source.ticket_attachment (
    id          BIGINT          NOT NULL,
    ticket_id   BIGINT          NULL,
    source_id   BIGINT          NOT NULL,
    file_name   VARCHAR(255)    NULL,
    file_path   TEXT            NULL,
    CONSTRAINT ticket_attachment_pkey PRIMARY KEY (id)
);

-- ============================================================================
-- Schema: public — 审核系统核心表
-- ============================================================================

-- ----------------------------------------------------------------------------
-- public.workorder_review — 审核元数据表
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.workorder_review (
    -- 主键（与 ticket_source.ticket.id 对应）
    id                      VARCHAR(64)     NOT NULL,

    -- 关联键（关联 ticket_source.ticket.ticket_no）
    ticket_no               VARCHAR(100)    NOT NULL,

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
    created_at              TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP       NOT NULL DEFAULT NOW(),

    CONSTRAINT workorder_review_pkey PRIMARY KEY (id),
    CONSTRAINT workorder_review_ticket_no_key UNIQUE (ticket_no)
);

-- workorder_review 索引（列表/统计/同步恢复/同步失败查询）
-- 注：本文件是唯一 DDL 权威（docker compose 启动时自动执行）；alembic 迁移为遗留
CREATE INDEX IF NOT EXISTS idx_review_status          ON public.workorder_review (review_status);
CREATE INDEX IF NOT EXISTS idx_review_status_created  ON public.workorder_review (review_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_review_sync_status     ON public.workorder_review (sync_status);
CREATE INDEX IF NOT EXISTS idx_review_sync_reviewed   ON public.workorder_review (sync_status, reviewed_at);
CREATE INDEX IF NOT EXISTS idx_review_created_at      ON public.workorder_review (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_review_updated_at      ON public.workorder_review (updated_at);
CREATE INDEX IF NOT EXISTS idx_review_sync_external_id ON public.workorder_review (sync_external_id);

-- ----------------------------------------------------------------------------
-- public.workorder_audit_log — 审核审计日志表
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.workorder_audit_log (
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

CREATE INDEX IF NOT EXISTS idx_workorder    ON public.workorder_audit_log (workorder_id);
CREATE INDEX IF NOT EXISTS idx_session      ON public.workorder_audit_log (session_id);
CREATE INDEX IF NOT EXISTS idx_operator     ON public.workorder_audit_log (operator_id);
CREATE INDEX IF NOT EXISTS idx_operated_at  ON public.workorder_audit_log (operated_at);

-- ----------------------------------------------------------------------------
-- public.bad_case_sample — AI 审核坏例样本表
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.bad_case_sample (
    id              BIGSERIAL       PRIMARY KEY,
    workorder_id    VARCHAR(64)     NOT NULL,
    audit_log_id    BIGINT          NOT NULL REFERENCES public.workorder_audit_log (id),
    field_path      VARCHAR(128)    NOT NULL,
    ai_value        TEXT            NULL,
    human_value     TEXT            NULL,
    sample_status   VARCHAR(16)     NOT NULL DEFAULT 'pending'
                    CHECK (sample_status IN ('pending', 'reviewed', 'accepted', 'rejected')),
    source          VARCHAR(32)     NOT NULL DEFAULT 'review_correction',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bcs_status    ON public.bad_case_sample (sample_status);
CREATE INDEX IF NOT EXISTS idx_bcs_workorder ON public.bad_case_sample (workorder_id);
CREATE INDEX IF NOT EXISTS idx_bcs_audit_log ON public.bad_case_sample (audit_log_id);

-- ----------------------------------------------------------------------------
-- public.workorder_stash — 审核进度暂存表
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.workorder_stash (
    id              BIGSERIAL       PRIMARY KEY,
    workorder_id    VARCHAR(64)     NOT NULL UNIQUE,
    field_states    JSONB           NOT NULL DEFAULT '{}'::jsonb,
    notes           TEXT            NULL DEFAULT '',
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP       NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- public.v_ticket — 工单业务数据视图（只读）
--
-- 从 ticket_source.ticket LEFT JOIN ticket_source.project_info 构建，
-- 提供审核模块统一的工单业务数据查询入口。
-- ============================================================================
CREATE OR REPLACE VIEW public.v_ticket AS
SELECT
    t.id,
    t.ticket_no,
    t."ownerId",
    t."dimDepart",
    t."entityType",
    t.name,
    t."caseSource",
    t."feedbackChannel__c",
    t."workOrderStatus__c",
    t."caseDescription",
    t."caseStatus",
    t."problemLevel__c",
    t."problemType1__c",
    t."problemType2__c",
    t."problemType3__c",
    t."feedbackCount__c",
    t."problemResponsible__c",
    t."problemDept__c",
    t."feedbackUserName__c",
    t."feedbackUserContact__c",
    t."needCallBack__c",
    t."isHandled__c",
    t."needOnSite__c",
    t.remark__c,
    t."relatedAttachment__c",
    t."planFeedbackTime__c",
    t."requireSolveTime__c",
    t."defectFlag__c",
    pi."caseAccountId",
    pi."custLevel1__c",
    pi."projectName__c",
    pi."projectProvince__c",
    pi."bigCustShortName__c",
    pi."serviceCycleStart__c",
    pi."serviceCycleEnd__c",
    pi."isOfflineApply__c",
    pi."isOverdueService__c"
FROM ticket_source.ticket t
LEFT JOIN ticket_source.project_info pi
    ON t."caseAccountId"::text = pi."caseAccountId"::text;

COMMIT;
