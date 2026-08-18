-- ============================================================================
-- 售后工单审核系统 — PostgreSQL 初始化 DDL
--
-- 与 ORM 模型严格同步（backend/app/models/），并从实际数据库导出验证。
-- 所有表均在 public schema（原 ticket_source 已合并）。
--
-- 表结构分两大类：
--
-- 【工单数据表】外部管道写入、本系统只读，共 8 张表
--   · ticket / project_info / source_message / ticket_attachment
--   · wechat_user / wechat_session / user_ledger / beisen_employee_cache
--   · ticket_view 为【服务工单】唯一视图，不属于外部 8 表
--
-- 【审查数据表】审核流程自身产生的数据 — 审核操作写入
--   · workorder_review      审核元数据（主表，通过 ticket_id 关联工单数据表）
--   · workorder_audit_log   审核审计日志
--   · bad_case_sample       坏例样本（模型回流）
--   · workorder_stash       审核进度暂存
--
-- 用法: psql -h localhost -U postgres -d customer_service_ticket -f schema_init.sql
-- ============================================================================

BEGIN;

-- ============================================================================
-- 一、工单数据表 — 仅供本地空库/集成测试初始化。
-- 生产环境的 8 张表由上游维护，本项目只创建审核表与 ticket_view。
-- ============================================================================

-- ----------------------------------------------------------------------------
-- wechat_user — 微信用户（发起人）【工单数据表】
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wechat_user (
    id          BIGSERIAL       PRIMARY KEY,
    user_id     VARCHAR(128)    NOT NULL UNIQUE,
    nick_name   VARCHAR(100)    NOT NULL
);

CREATE TABLE IF NOT EXISTS wechat_session (
    id              BIGSERIAL       PRIMARY KEY,
    customer_id     VARCHAR(128)    NOT NULL REFERENCES wechat_user (user_id),
    service_id      VARCHAR(128)    NULL,
    start_time      TIMESTAMPTZ     NULL,
    customer_msgs   JSONB           NOT NULL DEFAULT '[]'::jsonb,
    service_msgs    JSONB           NOT NULL DEFAULT '[]'::jsonb,
    source          VARCHAR(20)     NOT NULL DEFAULT '微信',
    status          VARCHAR(20)     NOT NULL DEFAULT 'pending',
    retry_count     INTEGER         NOT NULL DEFAULT 0,
    last_error      TEXT            NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_wechat_session_customer_start UNIQUE (customer_id, start_time)
);
CREATE INDEX IF NOT EXISTS ix_wechat_session_customer_id ON wechat_session (customer_id);
CREATE INDEX IF NOT EXISTS ix_wechat_session_status ON wechat_session (status);

-- ----------------------------------------------------------------------------
-- source_message — 消息来源【工单数据表】
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS source_message (
    id          BIGSERIAL       PRIMARY KEY,
    source      VARCHAR(20)     NOT NULL,
    content     TEXT            NOT NULL,
    msg_time    TIMESTAMPTZ     NULL,
    status      VARCHAR(20)     NOT NULL DEFAULT 'pending',
    retry_count INTEGER         NOT NULL DEFAULT 0,
    last_error  TEXT            NULL,
    created_at  TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP       NOT NULL DEFAULT NOW(),
    from_addr   VARCHAR(256)    NULL,
    to_addr     VARCHAR(256)    NULL
);

-- ----------------------------------------------------------------------------
-- project_info — 项目信息【工单数据表】
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS project_info (
    id                      BIGSERIAL       PRIMARY KEY,
    station_name            VARCHAR(200)    NULL,
    "caseAccountId"         VARCHAR(100)    NULL,
    "bigCustShortName_c"    VARCHAR(200)    NULL,
    "serviceCycleStart_c"   VARCHAR         NULL,
    "isOfflineApply_c"      BOOLEAN         NULL DEFAULT FALSE,
    "projectName_c"         VARCHAR(200)    NULL,
    "projectProvince_c"     VARCHAR(100)    NULL,
    "serviceCycleEnd_c"     VARCHAR         NULL,
    "isOverdueService_c"    VARCHAR         NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_project_info_station ON project_info (station_name);

CREATE TABLE IF NOT EXISTS user_ledger (
    id                      BIGSERIAL       PRIMARY KEY,
    user_id                 VARCHAR(128)    NULL UNIQUE,
    station_name            VARCHAR(200)    NULL,
    name                    VARCHAR(100)    NULL,
    phone                   VARCHAR(20)     NULL,
    province                VARCHAR(100)    NULL,
    case_account_id         VARCHAR(100)    NULL,
    project_name            VARCHAR(200)    NULL,
    customer_short_name     VARCHAR(200)    NULL,
    service_cycle_start     VARCHAR(100)    NULL,
    service_cycle_end       VARCHAR(100)    NULL,
    is_overdue_service      VARCHAR(20)     NULL,
    created_at              TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS beisen_employee_cache (
    id          BIGSERIAL       PRIMARY KEY,
    name        VARCHAR(100)    NOT NULL UNIQUE,
    user_id     INTEGER         NOT NULL,
    job_number  VARCHAR(64)     NOT NULL,
    dept_id     INTEGER         NULL,
    dept_name   VARCHAR(200)    NULL,
    status      INTEGER         NOT NULL,
    synced_at   TIMESTAMP       NOT NULL
);

-- ----------------------------------------------------------------------------
-- ticket — 工单业务数据（销售易 serviceCase API 字段）【工单数据表 · 主表】
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ticket (
    id                      BIGSERIAL       PRIMARY KEY,
    source_id               BIGINT          NULL UNIQUE REFERENCES source_message (id),
    session_id              BIGINT          NULL UNIQUE REFERENCES wechat_session (id),
    "ownerId"               VARCHAR(64)     NOT NULL,
    "dimDepart"             VARCHAR(64)     NOT NULL,
    "entityType"            VARCHAR(64)     NOT NULL,
    name                    VARCHAR(100)    NOT NULL,
    "case_Source"           VARCHAR(20)     NULL,
    "feedbackChannel_c"     VARCHAR(20)     NULL,
    "workOrderStatus__c"    VARCHAR(50)     NOT NULL,
    "caseDescription"       TEXT            NULL,
    "caseStatus"            VARCHAR(20)     NOT NULL,
    "problemLevel_c"        VARCHAR(20)     NULL,
    "problemResponsible_c"  VARCHAR(100)    NULL,
    "problemDept_c"         VARCHAR(100)    NULL,
    "problemType1__c"       VARCHAR(100)    NULL,
    "problemType2__c"       VARCHAR(100)    NULL,
    "problemType3__c"       VARCHAR(100)    NULL,
    "feedbackCount_c"       VARCHAR(100)    NULL,
    "needCallBack__c"       VARCHAR(4)      NULL,
    "isHandled__c"          VARCHAR(4)      NULL,
    "needOnSite__c"         VARCHAR(4)      NULL,
    remark__c               TEXT            NULL,
    "planFeedbackTime__c"   VARCHAR(100)    NULL,
    "requireSolveTime__c"   VARCHAR(100)    NULL,
    "defectFlag__c"         VARCHAR(4)      NULL DEFAULT '1',
    "feedbackUserName_c"    VARCHAR(100)    NULL,
    "feedbackUserContact_c" VARCHAR(200)    NULL,
    CONSTRAINT ck_ticket_source_or_session CHECK (source_id IS NOT NULL OR session_id IS NOT NULL)
);

-- ----------------------------------------------------------------------------
-- ticket_attachment — 工单附件【工单数据表】
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ticket_attachment (
    id          BIGSERIAL       PRIMARY KEY,
    ticket_id   BIGINT          NULL REFERENCES ticket (id),
    session_id  BIGINT          NULL REFERENCES wechat_session (id),
    source_id   BIGINT          NULL REFERENCES source_message (id),
    file_name   VARCHAR(255)    NULL,
    file_path   TEXT            NULL
);

-- ============================================================================
-- 二、审查数据表 — 审核流程数据（审核操作写入）
--   workorder_review / workorder_audit_log / bad_case_sample / workorder_stash
--   通过 workorder_review.ticket_id 关联【服务工单】ticket_view
-- ============================================================================

-- ----------------------------------------------------------------------------
-- public.workorder_review — 审核元数据表【审查数据表 · 主表】
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.workorder_review (
    -- 审核队列内部主键
    id                      VARCHAR(64)     NOT NULL,

    -- 关联键和导入幂等键（关联 ticket.id）
    ticket_id               BIGINT          NOT NULL REFERENCES public.ticket (id),

    -- 乐观锁版本号
    version                 INTEGER         NOT NULL DEFAULT 1,
    lock_fencing_token      BIGINT          NOT NULL DEFAULT 0,

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

    -- 审核编辑（JSONB，覆盖 ticket_view 字段值的增量修改）
    field_overrides         JSONB           NOT NULL DEFAULT '{}'::jsonb,

    -- 同步至销售易
    sync_status             VARCHAR(16)     NOT NULL DEFAULT 'pending'
                            CHECK (sync_status IN ('pending', 'syncing', 'synced', 'failed', 'uncertain')),
    sync_attempts           INTEGER         NOT NULL DEFAULT 0,
    sync_last_error         TEXT            NULL,
    sync_idempotency_key    VARCHAR(128)    NULL,
    sync_external_id        VARCHAR(64)     NULL,
    sync_started_at         TIMESTAMPTZ     NULL,

    -- 发起人信息（导入时冗余存储）
    initiator               VARCHAR(64)     NULL,
    initiator_department    VARCHAR(128)    NULL,

    -- 时间戳
    created_at              TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP       NOT NULL DEFAULT NOW(),

    CONSTRAINT workorder_review_pkey PRIMARY KEY (id),
    CONSTRAINT workorder_review_ticket_id_key UNIQUE (ticket_id)
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
-- public.workorder_audit_log — 审核审计日志表【审查数据表】
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
-- public.bad_case_sample — AI 审核坏例样本表【审查数据表】
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
-- public.workorder_stash — 审核进度暂存表【审查数据表】
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.workorder_stash (
    id              BIGSERIAL       PRIMARY KEY,
    workorder_id    VARCHAR(64)     NOT NULL UNIQUE,
    field_states    JSONB           NOT NULL DEFAULT '{}'::jsonb,
    notes           TEXT            NULL DEFAULT '',
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP       NOT NULL DEFAULT NOW()
);

-- 每次审核提交的幂等结果，覆盖零字段修改的直接通过场景
CREATE TABLE IF NOT EXISTS public.review_submission (
    idempotency_key VARCHAR(128) PRIMARY KEY,
    workorder_id    VARCHAR(64)  NOT NULL,
    session_id      VARCHAR(64)  NOT NULL,
    decision        VARCHAR(16)  NOT NULL,
    request_hash    VARCHAR(64)  NOT NULL,
    response_data   JSONB        NOT NULL,
    operator_id     VARCHAR(64)  NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_submission_session UNIQUE (workorder_id, session_id)
);
CREATE INDEX IF NOT EXISTS idx_submission_workorder ON public.review_submission (workorder_id);

-- ============================================================================
-- public.ticket_view — 【服务工单】唯一业务视图（只读）
--
-- 从 8 张源表构建，保持审核应用既有销售易字段名契约。
-- 提供审核模块统一的工单业务数据查询入口。
-- 审查数据表通过 workorder_review.ticket_id 关联本视图。
-- ============================================================================
DROP VIEW IF EXISTS public.ticket_view;
CREATE VIEW public.ticket_view AS
SELECT
    t.id,
    t."ownerId",
    t."dimDepart",
    t."entityType",
    t.name,
    t."case_Source" AS "caseSource",
    t."feedbackChannel_c" AS "feedbackChannel__c",
    t."workOrderStatus__c",
    t."caseDescription",
    t."caseStatus",
    t."problemLevel_c" AS "problemLevel__c",
    t."problemType1__c",
    t."problemType2__c",
    t."problemType3__c",
    t."feedbackCount_c" AS "feedbackCount__c",
    t."problemResponsible_c" AS "problemResponsible__c",
    t."problemDept_c" AS "problemDept__c",
    COALESCE(NULLIF(t."feedbackUserName_c", ''), ul.name, wu.nick_name,
             sm.from_addr) AS "feedbackUserName__c",
    COALESCE(NULLIF(t."feedbackUserContact_c", ''), ul.phone,
             sm.from_addr) AS "feedbackUserContact__c",
    t."needCallBack__c",
    t."isHandled__c",
    t."needOnSite__c",
    t.remark__c,
    att.paths AS "relatedAttachment__c",
    t."planFeedbackTime__c",
    t."requireSolveTime__c",
    t."defectFlag__c",
    COALESCE(ul.case_account_id, pi."caseAccountId") AS "caseAccountId",
    NULL::VARCHAR AS "custLevel1__c",
    COALESCE(ul.project_name, pi."projectName_c") AS "projectName__c",
    COALESCE(ul.province, pi."projectProvince_c") AS "projectProvince__c",
    COALESCE(ul.customer_short_name, pi."bigCustShortName_c") AS "bigCustShortName__c",
    COALESCE(ul.service_cycle_start, pi."serviceCycleStart_c") AS "serviceCycleStart__c",
    COALESCE(ul.service_cycle_end, pi."serviceCycleEnd_c") AS "serviceCycleEnd__c",
    CASE WHEN pi."isOfflineApply_c" IS TRUE THEN '1'
         WHEN pi."isOfflineApply_c" IS FALSE THEN '2' END AS "isOfflineApply__c",
    CASE lower(COALESCE(ul.is_overdue_service, pi."isOverdueService_c"))
         WHEN 'true' THEN '1' WHEN '1' THEN '1' WHEN 'y' THEN '1'
         WHEN 'false' THEN '2' WHEN '0' THEN '2' WHEN '2' THEN '2' WHEN 'n' THEN '2'
    END AS "isOverdueService__c",
    COALESCE(ul.station_name, pi.station_name) AS "stationName",
    COALESCE(ws.start_time, sm.msg_time, ws.created_at AT TIME ZONE 'Asia/Shanghai',
             sm.created_at AT TIME ZONE 'Asia/Shanghai') AS source_created_at
FROM ticket t
LEFT JOIN wechat_session ws ON ws.id = t.session_id
LEFT JOIN wechat_user wu ON wu.user_id = ws.customer_id
LEFT JOIN user_ledger ul ON ul.user_id = ws.customer_id
LEFT JOIN project_info pi ON pi.station_name = ul.station_name
LEFT JOIN source_message sm ON sm.id = t.source_id
LEFT JOIN LATERAL (
    SELECT string_agg(COALESCE(a.file_path, a.file_name), ', ' ORDER BY a.id) AS paths
    FROM ticket_attachment a
    WHERE a.ticket_id = t.id
       OR (a.ticket_id IS NULL AND t.session_id IS NOT NULL AND a.session_id = t.session_id)
       OR (a.ticket_id IS NULL AND t.source_id IS NOT NULL AND a.source_id = t.source_id)
) att ON TRUE;

COMMIT;
