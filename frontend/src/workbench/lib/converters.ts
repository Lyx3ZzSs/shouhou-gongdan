/**
 * 后端 API 类型 ↔ 工作台领域类型 转换函数。
 *
 * 三层分离中的第二层：api/review（纯 fetch）→ converters（转换）→ store（消费）。
 * 参考 React Query 的 select 模式——数据在进入 Store 前完成转换，Store 只存储工作台原生类型。
 */

import type {
  Anomaly,
  AuditLogEntry,
  ChangeRecord,
  FieldDef,
  FieldGroupId,
  QueueItem,
  ReviewTicket,
} from '../types';
import type {
  GeneratedWorkOrderSummary,
  GeneratedWorkOrderResponse,
  GeneratedAuditLogEntry,
} from '../../api/review';
import type { FieldChange } from '../../pages/WorkOrderReview/types';
import { nowIso } from './format';

// ---------------------------------------------------------------------------
// 1. 字段映射配置
// ---------------------------------------------------------------------------

interface FieldMapping {
  backendKey: string;
  id: string;
  name: string;
  group: FieldGroupId;
  type: FieldDef['type'];
  required?: boolean;
  isKey?: boolean;
  readonly?: boolean;
  options?: { label: string; value: string }[];
}

const ORDER_LEVEL_OPTIONS = [
  { label: 'P0 极度紧急', value: 'P0' },
  { label: 'P1 紧急', value: 'P1' },
  { label: 'P2 高', value: 'P2' },
  { label: 'P3 中', value: 'P3' },
  { label: 'P4 低', value: 'P4' },
];

const FEEDBACK_CHANNEL_OPTIONS = [
  { label: '400电话', value: '400电话' },
  { label: '企业微信', value: '企业微信' },
  { label: '邮件', value: '邮件' },
  { label: '小程序', value: '小程序' },
];

const FIELD_MAPPING: FieldMapping[] = [
  // ---- 基本信息 ----
  { backendKey: 'serial_number', id: 'serial_number', name: '工单编号', group: 'basic', type: 'text', readonly: true },
  { backendKey: 'created_at', id: 'created_at', name: '创建时间', group: 'basic', type: 'datetime', readonly: true },
  { backendKey: 'initiator', id: 'initiator', name: '发起人', group: 'basic', type: 'text', readonly: true },
  { backendKey: 'initiator_department', id: 'initiator_department', name: '发起部门', group: 'basic', type: 'text', readonly: true },
  { backendKey: 'project_code', id: 'project_code', name: '项目编码', group: 'basic', type: 'text', isKey: true },
  { backendKey: 'project_name', id: 'project_name', name: '项目名称', group: 'basic', type: 'text', isKey: true },

  // ---- 联系人 ----
  { backendKey: 'customer_name', id: 'customer_name', name: '客户名称', group: 'contact', type: 'text', required: true },
  { backendKey: 'responsible_person', id: 'responsible_person', name: '责任人', group: 'contact', type: 'text', required: true },
  { backendKey: 'responsible_department', id: 'responsible_department', name: '责任部门', group: 'contact', type: 'text' },
  { backendKey: 'after_sales_person', id: 'after_sales_person', name: '售后负责人', group: 'contact', type: 'text' },

  // ---- 描述 ----
  { backendKey: 'problem_description', id: 'problem_description', name: '问题描述', group: 'description', type: 'textarea', required: true, isKey: true },
  { backendKey: 'feedback_channel', id: 'feedback_channel', name: '反馈渠道', group: 'description', type: 'select', options: FEEDBACK_CHANNEL_OPTIONS },
  { backendKey: 'fault_detail', id: 'fault_detail', name: '故障详情', group: 'description', type: 'textarea' },

  // ---- 分类 ----
  { backendKey: 'problem_category_l1', id: 'problem_category_l1', name: '问题分类(L1)', group: 'category', type: 'select', required: true, options: [
    { label: '产品问题', value: '产品问题' }, { label: '数据问题', value: '数据问题' },
    { label: '工程问题', value: '工程问题' }, { label: '采购问题', value: '采购问题' },
    { label: '其他问题', value: '其他问题' },
  ]},
  { backendKey: 'problem_category_l2', id: 'problem_category_l2', name: '问题分类(L2)', group: 'category', type: 'select', options: [] },
  { backendKey: 'problem_category_l3', id: 'problem_category_l3', name: '问题分类(L3)', group: 'category', type: 'select', options: [] },
  { backendKey: 'order_type', id: 'order_type', name: '工单类型', group: 'category', type: 'select', options: [
    { label: '售后单', value: '售后单' }, { label: 'A类售后单', value: 'A类售后单' }, { label: '大客户售后单', value: '大客户售后单' },
  ]},
  { backendKey: 'problem_type', id: 'problem_type', name: '问题类型', group: 'category', type: 'text' },
  { backendKey: 'fault_category', id: 'fault_category', name: '故障类别', group: 'category', type: 'text' },
  { backendKey: 'product_line', id: 'product_line', name: '产品线', group: 'category', type: 'text' },
  { backendKey: 'product_category', id: 'product_category', name: '产品类别', group: 'category', type: 'text' },
  { backendKey: 'product_type', id: 'product_type', name: '产品型号', group: 'category', type: 'text' },
  { backendKey: 'customer_level', id: 'customer_level', name: '客户级别', group: 'category', type: 'text' },
  { backendKey: 'order_level', id: 'order_level', name: '工单级别', group: 'category', type: 'select', options: ORDER_LEVEL_OPTIONS },
  { backendKey: 'fault_level', id: 'fault_level', name: '故障级别', group: 'category', type: 'select', options: ORDER_LEVEL_OPTIONS },
  { backendKey: 'onsite_level', id: 'onsite_level', name: '现场级别', group: 'category', type: 'select', options: ORDER_LEVEL_OPTIONS },

  // ---- 地址 ----
  { backendKey: 'station_name', id: 'station_name', name: '场站名称', group: 'address', type: 'text', required: true },
  { backendKey: 'project_province', id: 'project_province', name: '省份', group: 'address', type: 'select', options: [
    { label: '北京', value: '北京' }, { label: '上海', value: '上海' }, { label: '广东', value: '广东' },
    { label: '浙江', value: '浙江' }, { label: '江苏', value: '江苏' }, { label: '四川', value: '四川' },
    { label: '湖北', value: '湖北' },
  ]},
  { backendKey: 'dispatch_name', id: 'dispatch_name', name: '调度名称', group: 'address', type: 'text' },

  // ---- 要求 ----
  { backendKey: 'required_solve_time', id: 'required_solve_time', name: '要求解决时限', group: 'requirement', type: 'datetime' },
  { backendKey: 'transferred_person', id: 'transferred_person', name: '转交人', group: 'requirement', type: 'text' },
  { backendKey: 'transferred_department', id: 'transferred_department', name: '转交部门', group: 'requirement', type: 'text' },
  { backendKey: 'primary_department', id: 'primary_department', name: '主责部门', group: 'requirement', type: 'text' },

  // ---- 系统（只读元数据） ----
  { backendKey: 'version', id: 'version', name: '数据版本', group: 'system', type: 'number', readonly: true },
  { backendKey: 'status', id: 'status', name: '审核状态', group: 'system', type: 'text', readonly: true },
  { backendKey: 'reject_count', id: 'reject_count', name: '驳回次数', group: 'system', type: 'number', readonly: true },
  { backendKey: 'last_reject_reason', id: 'last_reject_reason', name: '上次驳回原因', group: 'system', type: 'textarea', readonly: true },
  { backendKey: 'last_rejected_by', id: 'last_rejected_by', name: '上次驳回人', group: 'system', type: 'text', readonly: true },
  { backendKey: 'last_rejected_at', id: 'last_rejected_at', name: '上次驳回时间', group: 'system', type: 'datetime', readonly: true },
  { backendKey: 'ai_confidence', id: 'ai_confidence', name: 'AI 置信度', group: 'system', type: 'number', readonly: true },
];

const MAPPING_BY_KEY: Record<string, FieldMapping> = {};
for (const m of FIELD_MAPPING) {
  MAPPING_BY_KEY[m.backendKey] = m;
}

// ---------------------------------------------------------------------------
// 2. 摘要 → 队列项
// ---------------------------------------------------------------------------

export function workOrderSummaryToQueueItem(
  summary: GeneratedWorkOrderSummary,
): QueueItem {
  const status = normalizeStatus(summary.status);
  return {
    id: summary.id,
    serialNumber: summary.serial_number ?? '',
    title: summary.station_name ?? summary.customer_name ?? '未知工单',
    type: '',
    riskLevel: 'medium',
    status,
    anomalyCount: 0,
    slaRemainingMin: 480,
    createdAt: summary.created_at ?? nowIso(),
    urgency: 'medium',
  };
}

function normalizeStatus(s: string | null | undefined): QueueItem['status'] {
  switch (s) {
    case 'pending_review': return 'pending_review';
    case 'reviewing': return 'reviewing';
    case 'returned': return 'returned';
    case 'stashed': return 'stashed';
    default: return 'pending_review';
  }
}

// ---------------------------------------------------------------------------
// 3. 工单详情 → ReviewTicket
// ---------------------------------------------------------------------------

export function workOrderDataToReviewTicket(
  data: GeneratedWorkOrderResponse,
  auditLogs: AuditLogEntry[],
): ReviewTicket {
  const fields = buildFieldDefs(data);
  const anomalies = generateAnomalies(data, fields);

  return {
    id: data.id,
    serialNumber: data.serial_number ?? '',
    title: data.project_name ?? data.station_name ?? '未知工单',
    type: data.order_type ?? data.problem_type ?? '',
    urgency: deriveUrgency(data.order_level),
    riskLevel: deriveRiskLevel(data.order_level ?? data.fault_level),
    source: data.feedback_channel ?? '',
    status: normalizeStatus(data.status) as ReviewTicket['status'],
    createdAt: data.created_at ?? nowIso(),
    slaRemainingMin: computeSlaMinutes(data.required_solve_time),
    systemConfidence: data.ai_confidence != null ? Math.round(data.ai_confidence * 100) : 50,
    reviewer: '',
    version: data.version,
    fields,
    anomalies,
    auditLogs,
  };
}

function buildFieldDefs(data: GeneratedWorkOrderResponse): FieldDef[] {
  return FIELD_MAPPING.map((m) => {
    const raw = (data as Record<string, unknown>)[m.backendKey];
    const originalValue = raw == null ? '' : raw;
    return {
      id: m.id,
      name: m.name,
      group: m.group,
      originalValue,
      systemSuggestion: undefined,
      confidence: null,
      required: m.required,
      type: m.type,
      options: m.options ? [...m.options] : undefined,
      isKey: m.isKey,
      readonly: m.readonly,
    };
  });
}

// ---------------------------------------------------------------------------
// 4. 异常生成（基于业务规则）
// ---------------------------------------------------------------------------

export function generateAnomalies(
  data: GeneratedWorkOrderResponse,
  fields: FieldDef[],
): Anomaly[] {
  const anomalies: Anomaly[] = [];
  let idx = 0;
  const dataRecord = data as Record<string, unknown>;

  for (const m of FIELD_MAPPING) {
    const value = dataRecord[m.backendKey];

    // 必填字段为空 → blocking_error
    if (m.required && (value == null || value === '')) {
      anomalies.push({
        id: `anomaly-${idx++}`,
        type: 'blocking_error',
        fieldId: m.id,
        message: `${m.name}未填写（必填字段）`,
      });
    }

    // AI 置信度低于 0.6 且非只读字段 → warning
    if (
      !m.readonly &&
      data.ai_confidence != null &&
      data.ai_confidence < 0.6
    ) {
      anomalies.push({
        id: `anomaly-${idx++}`,
        type: 'warning',
        fieldId: m.id,
        message: `${m.name} 的 AI 置信度较低 (${Math.round(data.ai_confidence * 100)}%)，请重点审核`,
      });
    }
  }

  // 整体 AI 置信度低 → 全局 warning
  if (data.ai_confidence != null && data.ai_confidence < 0.6) {
    anomalies.push({
      id: `anomaly-${idx++}`,
      type: 'warning',
      message: `整体 AI 置信度仅 ${Math.round(data.ai_confidence * 100)}%，请仔细审核`,
    });
  }

  return anomalies;
}

// ---------------------------------------------------------------------------
// 5. 审计日志 session → 展平的条目
// ---------------------------------------------------------------------------

export function auditLogSessionsToEntries(
  sessions: GeneratedAuditLogEntry[],
): AuditLogEntry[] {
  const entries: AuditLogEntry[] = [];
  let uid = 0;

  for (const session of sessions) {
    for (const change of session.changes ?? []) {
      entries.push({
        id: `al-${uid++}`,
        timestamp: session.operated_at,
        category: change.op === 'replace' ? 'field_change' : 'process',
        actor: session.operator_name,
        action: `${opLabel(change.op)}「${change.field_label}」`,
        detail: change.old_value != null && change.new_value != null
          ? `${change.old_value} → ${change.new_value}`
          : undefined,
      });
    }
  }

  return entries;
}

function opLabel(op: string): string {
  switch (op) {
    case 'replace': return '修改';
    case 'add': return '添加';
    case 'remove': return '移除';
    default: return op;
  }
}

// ---------------------------------------------------------------------------
// 6. ChangeRecord → FieldChange（提交用）
// ---------------------------------------------------------------------------

/** 可转换为 FieldChange 的最小字段集合（ChangeRecord / EffectiveChange 均可）。 */
type ChangeLike = {
  fieldId: string;
  fieldName: string;
  before: unknown;
  after: unknown;
  kind: ChangeRecord['kind'] | string;
};

export function changeRecordToFieldChange(record: ChangeLike): FieldChange {
  return {
    op: kindToOp(record.kind),
    path: `/${record.fieldId}`,
    field_label: record.fieldName,
    old_value: record.before,
    new_value: record.after,
    ai_confidence: null,
  };
}

function kindToOp(kind: string): FieldChange['op'] {
  switch (kind) {
    case 'modify':
    case 'supplement':
    case 'confirm':
    case 'suggest':
      return 'replace';
    case 'reset':
      return 'replace';
    default:
      return 'replace';
  }
}

// ---------------------------------------------------------------------------
// 7. 辅助函数
// ---------------------------------------------------------------------------

function deriveRiskLevel(level: string | null | undefined): 'high' | 'medium' | 'low' {
  if (!level) return 'medium';
  const upper = level.toUpperCase();
  if (upper.startsWith('P0') || upper.startsWith('P1') || upper === '高') return 'high';
  if (upper.startsWith('P2') || upper.startsWith('P3') || upper === '中') return 'medium';
  if (upper.startsWith('P4') || upper === '低') return 'low';
  return 'medium';
}

function deriveUrgency(level: string | null | undefined): 'high' | 'medium' | 'low' {
  return deriveRiskLevel(level);
}

function computeSlaMinutes(requiredSolveTime: string | null | undefined): number {
  if (!requiredSolveTime) return 480;
  try {
    const target = new Date(requiredSolveTime).getTime();
    const now = Date.now();
    const remaining = Math.round((target - now) / 60_000);
    return Math.max(0, remaining);
  } catch {
    return 480;
  }
}
