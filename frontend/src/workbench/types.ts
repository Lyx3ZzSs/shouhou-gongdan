// 工单人工审核工作台 - 领域类型定义
// 按 spec 第十节字段状态类型与审核结论类型

export type FieldReviewStatus =
  | 'unchecked'
  | 'confirmed'
  | 'modified'
  | 'warning'
  | 'blocking_error';

export type ReviewDecision =
  | 'approved'
  | 'approved_with_changes'
  | 'rejected'
  | 'draft';

export type RiskLevel = 'high' | 'medium' | 'low';

export type AnomalyType = 'blocking_error' | 'warning' | 'info' | 'system_suggestion';

export type FieldGroupId =
  | 'basic'
  | 'contact'
  | 'description'
  | 'category'
  | 'address'
  | 'requirement'
  | 'attachment'
  | 'system';

export type FieldType =
  | 'text'
  | 'select'
  | 'textarea'
  | 'number'
  | 'phone'
  | 'datetime'
  | 'tags';

/** 字段定义（系统生成，只读元信息 + 原始值） */
export interface FieldDef {
  id: string;
  name: string;
  group: FieldGroupId;
  originalValue: unknown;
  systemSuggestion?: unknown;
  required?: boolean;
  type: FieldType;
  options?: { label: string; value: string }[];
  unit?: string;
  isKey?: boolean; // 关键字段
  readonly?: boolean; // 系统只读字段（如工单编号、创建时间）
}

/** 字段运行时状态（人工可编辑当前值 + 状态） */
export interface FieldState {
  fieldId: string;
  currentValue: unknown;
  baselineStatus: FieldReviewStatus; // 加载时的初始状态，重置时回到此状态
  status: FieldReviewStatus;
  remark?: string;
  changeReason?: string;
  changedAt?: string;
  uncertain?: boolean; // 标记为不确定（独立于 status）
}

/** 异常 / 风险提示 */
export interface Anomaly {
  id: string;
  type: AnomalyType;
  fieldId?: string; // 关联字段，可点击定位
  message: string;
}

/** 单次修改事件（追加日志，用于字段修改历史） */
export interface ChangeRecord {
  id: string;
  fieldId: string;
  fieldName: string;
  before: unknown;
  after: unknown;
  reason: string;
  timestamp: string;
  kind: 'modify' | 'supplement' | 'reset' | 'confirm' | 'suggest';
}

/** 审计时间线条目 */
export interface AuditLogEntry {
  id: string;
  timestamp: string;
  category: 'system' | 'field_change' | 'process' | 'comment' | 'external';
  actor: string;
  action: string;
  detail?: string;
}

/** 完整工单（当前审核对象） */
export interface ReviewTicket {
  id: string;
  serialNumber: string;
  title: string;
  type: string;
  urgency: 'high' | 'medium' | 'low';
  riskLevel: RiskLevel;
  source: string;
  status: 'pending_review' | 'reviewing' | 'returned' | 'rejected' | 'approved';
  createdAt: string;
  slaRemainingMin: number;
  reviewer: string;
  version: number;
  fields: FieldDef[];
  anomalies: Anomaly[];
  auditLogs: AuditLogEntry[];
}

/** 队列工单摘要 */
export interface QueueItem {
  id: string;
  serialNumber: string;
  title: string;
  type: string;
  source: string;
  riskLevel: RiskLevel;
  status: QueueItemStatus;
  anomalyCount: number;
  slaRemainingMin: number;
  createdAt: string;
  stashed?: boolean;
  lockedByOther?: string | null;
  hasValidationError?: boolean;
  modified?: boolean;
  urgency: 'high' | 'medium' | 'low';
}

export type QueueItemStatus = 'pending_review' | 'reviewing' | 'returned' | 'stashed';

/** 版本冲突信息 */
export interface ConflictInfo {
  otherUser: string;
  theirVersion: number;
  theirChanges: { fieldName: string; before: unknown; after: unknown }[];
}

export type AutoSaveStatus = 'idle' | 'saving' | 'saved' | 'failed' | 'offline';

/** 队列筛选条件 */
export interface QueueFilters {
  status: string; // 'all' | status values
  risk: string; // 'all' | high|medium|low
  type: string; // 'all' | type values
  source: string;
  sla: string; // 'all' | normal|warning|timeout
  validationError: boolean;
  modified: boolean;
  keyword: string;
}

export interface SavedView {
  id: string;
  name: string;
  filters: Partial<QueueFilters>;
}

/** 审核进度（派生） */
export interface ReviewProgress {
  total: number;
  confirmed: number;
  modified: number;
  pendingAnomalies: number;
  unconfirmedKeyFields: number;
}

/** 有效变更（派生：当前值与原始值不同的字段） */
export interface EffectiveChange {
  fieldId: string;
  fieldName: string;
  before: unknown;
  after: unknown;
  reason: string;
  changedAt: string;
  kind: ChangeRecord['kind'];
  group: FieldGroupId;
}

export type FieldFilter = 'all' | 'abnormal' | 'modified';
