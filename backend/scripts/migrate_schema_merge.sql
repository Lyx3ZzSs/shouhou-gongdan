-- ============================================================================
-- 迁移：合并两份表结构（ticket_source → public）
--
-- 将 ticket_source schema 的 5 张源表迁入 public，删除 ticket_source，
-- 重定义 ticket_view 视图引用 public.ticket / public.project_info。
-- 幂等性：重复执行会因表已在 public 而报错，仅在一次性迁移使用。
--
-- 回退：DROP VIEW IF EXISTS public.ticket_view;
--       ALTER TABLE public.wechat_user       SET SCHEMA ticket_source;
--       ALTER TABLE public.source_message    SET SCHEMA ticket_source;
--       ALTER TABLE public.project_info      SET SCHEMA ticket_source;
--       ALTER TABLE public.ticket            SET SCHEMA ticket_source;
--       ALTER TABLE public.ticket_attachment SET SCHEMA ticket_source;
--       CREATE SCHEMA IF NOT EXISTS ticket_source;
-- ============================================================================

BEGIN;

-- 1. 迁移 5 张源表到 public
ALTER TABLE ticket_source.wechat_user       SET SCHEMA public;
ALTER TABLE ticket_source.source_message    SET SCHEMA public;
ALTER TABLE ticket_source.project_info      SET SCHEMA public;
ALTER TABLE ticket_source.ticket            SET SCHEMA public;
ALTER TABLE ticket_source.ticket_attachment SET SCHEMA public;

-- 2. 删除已空的 ticket_source schema
DROP SCHEMA ticket_source;

-- 3. 重定义 ticket_view 视图（列清单与 schema_init.sql 一致）
CREATE OR REPLACE VIEW public.ticket_view AS
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
FROM public.ticket t
LEFT JOIN public.project_info pi
    ON t."caseAccountId"::text = pi."caseAccountId"::text;

COMMIT;
