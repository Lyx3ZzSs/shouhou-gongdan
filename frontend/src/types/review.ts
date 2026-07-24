// Shared types used by both the API client and converter layers.
// Originally in src/pages/WorkOrderReview/types.ts — moved here when the
// legacy WorkOrderReview page was removed.

export interface FieldChange {
  op: 'replace' | 'add' | 'remove';
  path: string;
  field_label: string;
  old_value: unknown;
  new_value: unknown;
  ai_confidence?: number | null;
}

export interface ReviewRequest {
  session_id: string;
  version: number;
  changes: FieldChange[];
  reject_reason: string | null;
}

export interface ReviewResponse {
  review_id: string;
  workorder_id: string;
  status: 'confirmed' | 'rejected';
  change_count: number;
  bad_case_count: number;
  next_status: string;
}

export interface WorkOrderData {
  id: string;
  version: number;
  status: string;
  reject_count: number;
  last_reject_reason: string | null;
  last_rejected_by: string | null;
  last_rejected_at: string | null;
  review_notes: string | null;
  ai_confidence?: number | null;

  // 销售易 serviceCase API 业务字段
  ownerId: string;
  dimDepart: string;
  entityType: string;
  name: string;
  caseSource: string;
  feedbackChannel__c: string;
  workOrderStatus__c: string;
  caseDescription: string;
  caseStatus: string;
  caseAccountId: string;
  custLevel1__c: string;
  projectName__c: string;
  projectProvince__c: string;
  bigCustShortName__c: string;
  serviceCycleStart__c: string;
  serviceCycleEnd__c: string;
  isOfflineApply__c: string;
  isOverdueService__c: string;
  problemLevel__c: string;
  problemType1__c: string;
  problemType2__c: string;
  problemType3__c: string;
  feedbackCount__c: string;
  problemResponsible__c: string;
  problemDept__c: string;
  feedbackUserName__c: string;
  feedbackUserContact__c: string;
  needCallBack__c: string;
  isHandled__c: string;
  needOnSite__c: string;
  remark__c: string;
  relatedAttachment__c: string;
  planFeedbackTime__c: string;
  requireSolveTime__c: string;
  defectFlag__c: string;

  // 只读字段
  serial_number: string;
  created_at: string;
  initiator: string;
  initiator_department: string;
  [key: string]: unknown;
}

export interface LockStatus {
  locked: boolean;
  owner?: string;
  locked_minutes?: number;
}

export interface AuditLogSession {
  session_id: string;
  operator_name: string;
  operated_at: string;
  changes: FieldChange[];
}

export const EXCEPTION_RULES = {
  missing_province: { field: 'projectProvince__c', message: '项目省份未填写' },
  missing_category: { field: 'problemType1__c', message: '问题分类-1级未选择' },
  missing_assignee: { field: 'problemResponsible__c', message: '问题责任人未分配' },
} as const;
