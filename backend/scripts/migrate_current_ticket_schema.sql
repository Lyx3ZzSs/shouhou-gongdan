-- 在 customer_service_ticket 的现行 8 张源表上安装审核系统对象。
-- 源表只读：本脚本仅创建审核表、索引和【服务工单】ticket_view。
BEGIN;

DO $$
DECLARE missing text;
BEGIN
    SELECT string_agg(name, ', ')
    INTO missing
    FROM unnest(ARRAY[
        'ticket', 'project_info', 'source_message', 'ticket_attachment',
        'wechat_user', 'wechat_session', 'user_ledger', 'beisen_employee_cache'
    ]) AS name
    WHERE to_regclass('public.' || name) IS NULL;
    IF missing IS NOT NULL THEN
        RAISE EXCEPTION '缺少现行工单源表: %', missing;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.workorder_review (
    id VARCHAR(64) PRIMARY KEY,
    ticket_id BIGINT NOT NULL UNIQUE REFERENCES public.ticket (id),
    version INTEGER NOT NULL DEFAULT 1,
    lock_fencing_token BIGINT NOT NULL DEFAULT 0,
    review_status VARCHAR(32) NOT NULL DEFAULT 'pending_review',
    reviewed_at TIMESTAMP NULL,
    reviewed_by VARCHAR(64) NULL,
    reject_count INTEGER NOT NULL DEFAULT 0,
    last_reject_reason TEXT NULL,
    last_rejected_by VARCHAR(64) NULL,
    last_rejected_at TIMESTAMP NULL,
    review_notes TEXT NULL,
    review_started_at TIMESTAMPTZ NULL,
    review_duration_seconds INTEGER NULL,
    field_overrides JSONB NOT NULL DEFAULT '{}'::jsonb,
    sync_status VARCHAR(16) NOT NULL DEFAULT 'pending'
        CHECK (sync_status IN ('pending', 'syncing', 'synced', 'failed', 'uncertain')),
    sync_attempts INTEGER NOT NULL DEFAULT 0,
    sync_last_error TEXT NULL,
    sync_idempotency_key VARCHAR(128) NULL,
    sync_external_id VARCHAR(64) NULL,
    sync_started_at TIMESTAMPTZ NULL,
    initiator VARCHAR(64) NULL,
    initiator_department VARCHAR(128) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_review_status ON workorder_review (review_status);
CREATE INDEX IF NOT EXISTS idx_review_status_created ON workorder_review (review_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_review_sync_status ON workorder_review (sync_status);
CREATE INDEX IF NOT EXISTS idx_review_sync_reviewed ON workorder_review (sync_status, reviewed_at);
CREATE INDEX IF NOT EXISTS idx_review_created_at ON workorder_review (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_review_updated_at ON workorder_review (updated_at);
CREATE INDEX IF NOT EXISTS idx_review_sync_external_id ON workorder_review (sync_external_id);

CREATE TABLE IF NOT EXISTS public.workorder_audit_log (
    id BIGSERIAL PRIMARY KEY,
    workorder_id VARCHAR(64) NOT NULL,
    session_id VARCHAR(64) NOT NULL,
    field_path VARCHAR(128) NOT NULL,
    field_label VARCHAR(64) NOT NULL,
    old_value TEXT NULL,
    new_value TEXT NULL,
    change_type VARCHAR(16) NOT NULL DEFAULT 'replace'
        CHECK (change_type IN ('replace', 'add', 'remove', 'rejected')),
    operator_id VARCHAR(64) NOT NULL,
    operator_name VARCHAR(64) NULL,
    operated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_workorder ON workorder_audit_log (workorder_id);
CREATE INDEX IF NOT EXISTS idx_session ON workorder_audit_log (session_id);
CREATE INDEX IF NOT EXISTS idx_operator ON workorder_audit_log (operator_id);
CREATE INDEX IF NOT EXISTS idx_operated_at ON workorder_audit_log (operated_at);

CREATE TABLE IF NOT EXISTS public.bad_case_sample (
    id BIGSERIAL PRIMARY KEY,
    workorder_id VARCHAR(64) NOT NULL,
    audit_log_id BIGINT NOT NULL REFERENCES workorder_audit_log (id),
    field_path VARCHAR(128) NOT NULL,
    ai_value TEXT NULL,
    human_value TEXT NULL,
    sample_status VARCHAR(16) NOT NULL DEFAULT 'pending'
        CHECK (sample_status IN ('pending', 'reviewed', 'accepted', 'rejected')),
    source VARCHAR(32) NOT NULL DEFAULT 'review_correction',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bcs_status ON bad_case_sample (sample_status);
CREATE INDEX IF NOT EXISTS idx_bcs_workorder ON bad_case_sample (workorder_id);
CREATE INDEX IF NOT EXISTS idx_bcs_audit_log ON bad_case_sample (audit_log_id);

CREATE TABLE IF NOT EXISTS public.workorder_stash (
    id BIGSERIAL PRIMARY KEY,
    workorder_id VARCHAR(64) NOT NULL UNIQUE,
    field_states JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes TEXT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.review_submission (
    idempotency_key VARCHAR(128) PRIMARY KEY,
    workorder_id VARCHAR(64) NOT NULL,
    session_id VARCHAR(64) NOT NULL,
    decision VARCHAR(16) NOT NULL,
    request_hash VARCHAR(64) NOT NULL,
    response_data JSONB NOT NULL,
    operator_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_submission_session UNIQUE (workorder_id, session_id)
);
CREATE INDEX IF NOT EXISTS idx_submission_workorder ON review_submission (workorder_id);

DROP VIEW IF EXISTS public.v_ticket;
DROP VIEW IF EXISTS public.ticket_view;
CREATE VIEW public.ticket_view AS
SELECT
    t.id, t."ownerId", t."dimDepart", t."entityType", t.name,
    t."case_Source" AS "caseSource",
    t."feedbackChannel_c" AS "feedbackChannel__c",
    t."workOrderStatus__c", t."caseDescription", t."caseStatus",
    t."problemLevel_c" AS "problemLevel__c",
    t."problemType1__c", t."problemType2__c", t."problemType3__c",
    t."feedbackCount_c" AS "feedbackCount__c",
    t."problemResponsible_c" AS "problemResponsible__c",
    t."problemDept_c" AS "problemDept__c",
    COALESCE(NULLIF(t."feedbackUserName_c", ''), ul.name, wu.nick_name, sm.from_addr)
        AS "feedbackUserName__c",
    COALESCE(NULLIF(t."feedbackUserContact_c", ''), ul.phone, sm.from_addr)
        AS "feedbackUserContact__c",
    t."needCallBack__c", t."isHandled__c", t."needOnSite__c", t.remark__c,
    att.paths AS "relatedAttachment__c",
    t."planFeedbackTime__c", t."requireSolveTime__c", t."defectFlag__c",
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

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'shouhou_review_app') THEN
        GRANT SELECT ON public.ticket_view TO shouhou_review_app;
    END IF;
END $$;

COMMIT;
