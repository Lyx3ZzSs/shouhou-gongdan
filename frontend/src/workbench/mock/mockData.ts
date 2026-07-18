import type {
  Anomaly,
  AuditLogEntry,
  FieldDef,
  QueueItem,
  ReviewTicket,
} from '../types';

/** 字段模板 — 使用与 converters.ts FIELD_MAPPING 一致的字段 ID，确保 mock 和真实数据走同一路径 */
export const FIELD_TEMPLATE: FieldDef[] = [
  // ---- 基本信息 ----
  { id: 'serial_number', name: '工单编号', group: 'basic', type: 'text', originalValue: 'WO-20260717-0381', readonly: true },
  { id: 'created_at', name: '创建时间', group: 'basic', type: 'datetime', originalValue: '2026-07-17T10:42:00', readonly: true },
  { id: 'initiator', name: '发起人', group: 'basic', type: 'text', originalValue: '系统自动', readonly: true },
  { id: 'initiator_department', name: '发起部门', group: 'basic', type: 'text', originalValue: '监控告警平台', readonly: true },
  { id: 'project_code', name: '项目编码', group: 'basic', type: 'text', originalValue: 'PRJ-2024-0812', isKey: true },
  { id: 'project_name', name: '项目名称', group: 'basic', type: 'text', originalValue: '东京二区设备故障报修', isKey: true },

  // ---- 联系人与服务对象 ----
  { id: 'customer_name', name: '客户名称', group: 'contact', type: 'text', originalValue: '东京二区 7-11 便利店（新宿店）', required: true },
  { id: 'responsible_person', name: '责任人', group: 'contact', type: 'text', originalValue: '佐藤健', required: true },
  { id: 'responsible_department', name: '责任部门', group: 'contact', type: 'text', originalValue: '运维部' },
  { id: 'after_sales_person', name: '售后负责人', group: 'contact', type: 'text', originalValue: '张三' },

  // ---- 问题描述 ----
  { id: 'problem_description', name: '问题描述', group: 'description', type: 'textarea', originalValue: '设备完全停机，无法运行，现场有焦糊味。', required: true, isKey: true },
  { id: 'feedback_channel', name: '反馈渠道', group: 'description', type: 'select', originalValue: '400电话', options: [
    { label: '400电话', value: '400电话' }, { label: '企业微信', value: '企业微信' },
    { label: '邮件', value: '邮件' }, { label: '小程序', value: '小程序' },
  ]},
  { id: 'fault_detail', name: '故障详情', group: 'description', type: 'textarea', originalValue: '变频器完全停机，现场有焦糊味，初步判断为过载导致。' },

  // ---- 分类与优先级 ----
  { id: 'problem_category_l1', name: '问题分类(L1)', group: 'category', type: 'select', originalValue: '产品问题', required: true, options: [
    { label: '产品问题', value: '产品问题' }, { label: '数据问题', value: '数据问题' },
    { label: '工程问题', value: '工程问题' }, { label: '采购问题', value: '采购问题' },
  ]},
  { id: 'problem_category_l2', name: '问题分类(L2)', group: 'category', type: 'select', originalValue: '', options: [] },
  { id: 'problem_category_l3', name: '问题分类(L3)', group: 'category', type: 'select', originalValue: '', options: [] },
  { id: 'order_type', name: '工单类型', group: 'category', type: 'select', originalValue: '售后单', isKey: true, options: [
    { label: '售后单', value: '售后单' }, { label: 'A类售后单', value: 'A类售后单' }, { label: '大客户售后单', value: '大客户售后单' },
  ]},
  { id: 'problem_type', name: '问题类型', group: 'category', type: 'text', originalValue: '设备故障' },
  { id: 'fault_category', name: '故障类别', group: 'category', type: 'text', originalValue: '变频器故障' },
  { id: 'product_line', name: '产品线', group: 'category', type: 'text', originalValue: '新能源设备' },
  { id: 'product_category', name: '产品类别', group: 'category', type: 'text', originalValue: '变频器' },
  { id: 'product_type', name: '产品型号', group: 'category', type: 'text', originalValue: 'XYZ-2000', systemSuggestion: 'XYZ-2000 变频器' },
  { id: 'customer_level', name: '客户级别', group: 'category', type: 'text', originalValue: 'A级' },
  { id: 'order_level', name: '工单级别', group: 'category', type: 'select', originalValue: 'P1', isKey: true, options: [
    { label: 'P0 极度紧急', value: 'P0' }, { label: 'P1 紧急', value: 'P1' },
    { label: 'P2 高', value: 'P2' }, { label: 'P3 中', value: 'P3' }, { label: 'P4 低', value: 'P4' },
  ]},
  { id: 'fault_level', name: '故障级别', group: 'category', type: 'select', originalValue: 'P2', options: [
    { label: 'P0 极度紧急', value: 'P0' }, { label: 'P1 紧急', value: 'P1' },
    { label: 'P2 高', value: 'P2' }, { label: 'P3 中', value: 'P3' }, { label: 'P4 低', value: 'P4' },
  ]},
  { id: 'onsite_level', name: '现场级别', group: 'category', type: 'select', originalValue: 'P2', options: [
    { label: 'P0 极度紧急', value: 'P0' }, { label: 'P1 紧急', value: 'P1' },
    { label: 'P2 高', value: 'P2' }, { label: 'P3 中', value: 'P3' }, { label: 'P4 低', value: 'P4' },
  ]},

  // ---- 地址与区域 ----
  { id: 'station_name', name: '场站名称', group: 'address', type: 'text', originalValue: '东京二区新宿站', required: true },
  { id: 'project_province', name: '省份', group: 'address', type: 'select', originalValue: '广东', isKey: true, options: [
    { label: '北京', value: '北京' }, { label: '上海', value: '上海' }, { label: '广东', value: '广东' },
    { label: '浙江', value: '浙江' }, { label: '江苏', value: '江苏' }, { label: '四川', value: '四川' },
  ]},
  { id: 'dispatch_name', name: '调度名称', group: 'address', type: 'text', originalValue: '东京二区调度中心' },

  // ---- 处理要求 ----
  { id: 'required_solve_time', name: '要求解决时限', group: 'requirement', type: 'datetime', originalValue: '2026-07-17T18:00:00' },
  { id: 'transferred_person', name: '转交人', group: 'requirement', type: 'text', originalValue: '' },
  { id: 'transferred_department', name: '转交部门', group: 'requirement', type: 'text', originalValue: '' },
  { id: 'primary_department', name: '主责部门', group: 'requirement', type: 'text', originalValue: '运维部' },

  // ---- 系统生成信息 ----
  { id: 'version', name: '数据版本', group: 'system', type: 'number', originalValue: 2, readonly: true },
  { id: 'status', name: '审核状态', group: 'system', type: 'text', originalValue: 'pending_review', readonly: true },
  { id: 'reject_count', name: '驳回次数', group: 'system', type: 'number', originalValue: 0, readonly: true },
  { id: 'last_reject_reason', name: '上次驳回原因', group: 'system', type: 'textarea', originalValue: '', readonly: true },
  { id: 'last_rejected_by', name: '上次驳回人', group: 'system', type: 'text', originalValue: '', readonly: true },
  { id: 'last_rejected_at', name: '上次驳回时间', group: 'system', type: 'datetime', originalValue: '', readonly: true },
];

/** 异常模板（6 条：1 阻断 / 3 风险 / 1 信息 / 1 系统建议） */
export const ANOMALY_TEMPLATE: Anomaly[] = [
  { id: 'a1', type: 'blocking_error', fieldId: 'customer_name', message: '客户名称缺失（必填字段未填写）' },
  { id: 'a2', type: 'warning', fieldId: 'fault_level', message: '故障等级与故障描述不一致：描述为"完全停机"但等级为"P2"' },
  { id: 'a3', type: 'warning', fieldId: 'project_province', message: '项目省份数据异常，请重点审核' },
  { id: 'a4', type: 'warning', fieldId: 'order_type', message: '工单类型发生过规则覆盖（系统覆盖为"售后单"）' },
  { id: 'a5', type: 'info', fieldId: 'feedback_channel', message: '来源为400电话，建议核实现场情况' },
  { id: 'a6', type: 'system_suggestion', fieldId: 'product_type', message: '建议产品型号使用"XYZ-2000 变频器"' },
];

/** 审计时间线模板（覆盖 system/external/process/field_change） */
export const AUDIT_TEMPLATE: AuditLogEntry[] = [
  { id: 'l1', timestamp: '2026-07-17T10:42:00', category: 'system', actor: '监控告警平台', action: '系统自动生成工单', detail: '告警 #A-9981 触发' },
  { id: 'l3', timestamp: '2026-07-17T10:43:00', category: 'external', actor: '系统', action: '工单类型规则覆盖', detail: '自动分类为「售后单」' },
  { id: 'l4', timestamp: '2026-07-17T10:44:00', category: 'process', actor: '李四', action: '转交至 张三', detail: '二线转单' },
  { id: 'l5', timestamp: '2026-07-17T10:45:00', category: 'process', actor: '张三', action: '开始审核' },
  { id: 'l6', timestamp: '2026-07-17T10:46:00', category: 'field_change', actor: '张三', action: '修改「工单类型」', detail: '售后单 → 大客户售后单' },
  { id: 'l7', timestamp: '2026-07-17T10:48:00', category: 'field_change', actor: '张三', action: '修改「省份」', detail: '广东 → 浙江' },
];

/** 主工单预置修改（演示"已产生多项人工修改"状态） */
export const PRESEEDED: Record<string, { currentValue: unknown; reason: string; changedAt: string }> = {
  order_type: { currentValue: '大客户售后单', reason: 'rule_mismatch', changedAt: '2026-07-17T10:46:00' },
  project_province: { currentValue: '浙江', reason: 'system_error', changedAt: '2026-07-17T10:48:00' },
};

/** 主工单 ID */
export const MAIN_TICKET_ID = 'wo-0381';

/** 队列（8 条，覆盖不同状态/风险/SLA/异常/暂存/被编辑） */
export const QUEUE: QueueItem[] = [
  {
    id: 'wo-0381', serialNumber: 'WO-20260717-0381', title: '设备故障报修', type: '设备故障', source: '监控告警自动生成',
    riskLevel: 'high', status: 'pending_review', anomalyCount: 6, slaRemainingMin: 36,
    createdAt: '2026-07-17T10:42:00', modified: true, urgency: 'medium', hasValidationError: true,
  },
  {
    id: 'wo-0379', serialNumber: 'WO-20260717-0379', title: '网络链路中断', type: '网络异常', source: '监控告警自动生成',
    riskLevel: 'high', status: 'pending_review', anomalyCount: 4, slaRemainingMin: 12,
    createdAt: '2026-07-17T10:30:00', urgency: 'high', hasValidationError: true,
  },
  {
    id: 'wo-0377', serialNumber: 'WO-20260717-0377', title: '制冷系统报警', type: '设备故障', source: '用户报修',
    riskLevel: 'medium', status: 'pending_review', anomalyCount: 3, slaRemainingMin: 95,
    createdAt: '2026-07-17T09:55:00', urgency: 'medium',
  },
  {
    id: 'wo-0375', serialNumber: 'WO-20260717-0375', title: '门禁异常', type: '设备异常', source: '巡检上报',
    riskLevel: 'low', status: 'returned', anomalyCount: 2, slaRemainingMin: 200,
    createdAt: '2026-07-17T09:20:00', urgency: 'low',
  },
  {
    id: 'wo-0372', serialNumber: 'WO-20260717-0372', title: '巡检发现异响', type: '巡检任务', source: '巡检上报',
    riskLevel: 'medium', status: 'pending_review', anomalyCount: 1, slaRemainingMin: 150,
    createdAt: '2026-07-17T08:40:00', urgency: 'medium', hasValidationError: true,
  },
  {
    id: 'wo-0369', serialNumber: 'WO-20260717-0369', title: 'UPS 电池告警', type: '设备故障', source: '二线转单',
    riskLevel: 'high', status: 'pending_review', anomalyCount: 5, slaRemainingMin: 28,
    createdAt: '2026-07-17T08:10:00', urgency: 'high', lockedByOther: '李四',
  },
  {
    id: 'wo-0365', serialNumber: 'WO-20260717-0365', title: '监控摄像头离线', type: '设备异常', source: '监控告警自动生成',
    riskLevel: 'low', status: 'stashed', anomalyCount: 2, slaRemainingMin: 300,
    createdAt: '2026-07-17T07:50:00', urgency: 'low', stashed: true,
  },
  {
    id: 'wo-0361', serialNumber: 'WO-20260717-0361', title: '空调不制冷', type: '设备故障', source: '用户报修',
    riskLevel: 'medium', status: 'pending_review', anomalyCount: 0, slaRemainingMin: 240,
    createdAt: '2026-07-17T07:10:00', urgency: 'medium',
  },
];

/** 版本冲突演示数据（李四在更高版本修改了紧急程度） */
export const CONFLICT_DEMO = {
  otherUser: '李四',
  theirVersion: 3,
  theirChanges: [{ fieldName: '紧急程度', before: '中', after: '高' }],
};

function pickAnomalies(count: number): Anomaly[] {
  if (count <= 0) return [];
  // 优先阻断 + 风险，保证演示有看点
  return ANOMALY_TEMPLATE.slice(0, Math.min(count, ANOMALY_TEMPLATE.length));
}

/** 根据队列项构建完整工单。主工单含预置修改；其余工单为干净待审状态。 */
export function buildTicket(item: QueueItem): ReviewTicket {
  const isMain = item.id === MAIN_TICKET_ID;
  const fields = FIELD_TEMPLATE.map((f) => ({
    ...f,
    ...(f.id === 'serial_number' ? { originalValue: item.serialNumber } : {}),
    ...(f.id === 'project_name' ? { originalValue: item.title } : {}),
    ...(f.id === 'order_type' ? { originalValue: isMain ? '售后单' : item.type } : {}),
    ...(f.id === 'fault_level' ? { originalValue: isMain ? 'P2' : item.riskLevel === 'high' ? 'P1' : item.riskLevel === 'medium' ? 'P2' : 'P3' } : {}),
    ...(f.id === 'created_at' ? { originalValue: item.createdAt } : {}),
    ...(f.id === 'feedback_channel' ? { originalValue: item.source } : {}),
  }));

  const anomalies = isMain ? ANOMALY_TEMPLATE : pickAnomalies(item.anomalyCount);

  const auditLogs: AuditLogEntry[] = isMain
    ? AUDIT_TEMPLATE
    : [
        ...AUDIT_TEMPLATE.filter((l) => l.category !== 'field_change'),
        {
          id: 'l-start',
          timestamp: item.createdAt,
          category: 'process' as const,
          actor: '张三',
          action: '开始审核',
        },
      ];

  return {
    id: item.id,
    serialNumber: item.serialNumber,
    title: item.title,
    type: item.type,
    urgency: item.urgency,
    riskLevel: item.riskLevel,
    source: item.source,
    status: item.status === 'stashed' ? 'pending_review' : item.status as ReviewTicket['status'],
    createdAt: item.createdAt,
    slaRemainingMin: item.slaRemainingMin,
    reviewer: '张三',
    version: isMain ? 2 : 1,
    fields,
    anomalies,
    auditLogs,
  };
}
