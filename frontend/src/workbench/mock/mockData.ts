import type {
  Anomaly,
  AuditLogEntry,
  FieldDef,
  QueueItem,
  ReviewTicket,
} from '../types';

/** 字段模板 — 使用与 converters.ts FIELD_MAPPING 一致的字段 ID，确保 mock 和真实数据走同一路径 */
export const FIELD_TEMPLATE: FieldDef[] = [
  // ---- 基本信息 (basic) ----
  { id: 'ownerId', name: '所有人', group: 'basic', type: 'text', originalValue: 'EMP000123', required: true },
  { id: 'dimDepart', name: '所属部门', group: 'basic', type: 'text', originalValue: 'DEPT001', required: true },
  { id: 'entityType', name: '业务类型', group: 'basic', type: 'text', originalValue: '11010045500001', readonly: true },
  { id: 'name', name: '工单主题', group: 'basic', type: 'text', originalValue: '东京二区设备故障报修', required: true, isKey: true },
  { id: 'caseStatus', name: '工单状态', group: 'basic', type: 'select', originalValue: '1', required: true, options: [
    { label: '待分配-1', value: '1' }, { label: '待处理-2', value: '2' },
    { label: '处理中-3', value: '3' }, { label: '待确认-4', value: '4' },
    { label: '已完成-5', value: '5' }, { label: '待回访-6', value: '6' },
  ]},
  { id: 'created_at', name: '创建时间', group: 'basic', type: 'datetime', originalValue: '2026-07-17T10:42:00', readonly: true },

  // ---- 工单分类 (category) ----
  { id: 'caseSource', name: '工单来源', group: 'category', type: 'select', originalValue: '1', required: true, options: [
    { label: '语音-1', value: '1' }, { label: '小组件-2', value: '2' }, { label: '留言-3', value: '3' },
    { label: '意见反馈-4', value: '4' }, { label: '其他-5', value: '5' },
  ]},
  { id: 'workOrderStatus__c', name: '工单类型', group: 'category', type: 'select', originalValue: '1', required: true, options: [
    { label: '售后单-1', value: '1' }, { label: '投诉单-2', value: '2' },
    { label: 'A类售后单-3', value: '3' }, { label: '大客户售后单-5', value: '5' },
  ]},
  { id: 'problemLevel__c', name: '问题等级', group: 'category', type: 'select', originalValue: '2', options: [
    { label: '常规问题-1', value: '1' }, { label: '重要紧急-2', value: '2' },
  ]},
  { id: 'problemType1__c', name: '问题分类-1级', group: 'category', type: 'select', originalValue: '1', options: [
    { label: '现场问题-1', value: '1' }, { label: '数据优化-2', value: '2' },
    { label: '报告/回函-3', value: '3' }, { label: '其他-6', value: '6' },
  ]},
  { id: 'problemType2__c', name: '问题分类-2级', group: 'category', type: 'select', originalValue: '1', options: [
    { label: '系统问题-1', value: '1' }, { label: '硬件故障 / 更换-2', value: '2' },
    { label: '其他-13', value: '13' },
  ]},
  { id: 'problemType3__c', name: '问题分类-3级', group: 'category', type: 'select', originalValue: '6', options: [
    { label: '系统 BUG-6', value: '6' }, { label: '配置问题-5', value: '5' },
    { label: '数据治理-4', value: '4' },
  ]},

  // ---- 客户与项目 (project) ----
  { id: 'bigCustShortName__c', name: '大客户简称', group: 'project', type: 'text', originalValue: '东京二区便利店' },
  { id: 'custLevel1__c', name: '客户级别', group: 'project', type: 'text', originalValue: 'A级' },
  { id: 'projectName__c', name: '项目名称', group: 'project', type: 'text', originalValue: 'XSJH20260723012', isKey: true },
  { id: 'projectProvince__c', name: '项目省份', group: 'project', type: 'text', originalValue: '广东' },
  { id: 'caseAccountId', name: '场站名称', group: 'project', type: 'text', originalValue: 'SPCZ202408210132' },

  // ---- 服务周期 (service_period) ----
  { id: 'serviceCycleStart__c', name: '周期服务开始时间', group: 'service_period', type: 'datetime', originalValue: '1784797500' },
  { id: 'serviceCycleEnd__c', name: '周期服务结束时间', group: 'service_period', type: 'datetime', originalValue: '1784797500' },
  { id: 'isOfflineApply__c', name: '是否线下申请', group: 'service_period', type: 'select', originalValue: '1', options: [
    { label: '是-1', value: '1' }, { label: '否-2', value: '2' },
  ]},
  { id: 'isOverdueService__c', name: '是否超期服务', group: 'service_period', type: 'select', originalValue: '2', options: [
    { label: '是-1', value: '1' }, { label: '否-2', value: '2' },
  ]},

  // ---- 问题描述 (description) ----
  { id: 'caseDescription', name: '工单描述', group: 'description', type: 'textarea', originalValue: '设备完全停机，无法运行，现场有焦糊味。', required: true, isKey: true },
  { id: 'remark__c', name: '备注', group: 'description', type: 'textarea', originalValue: '客户已多次催促，需紧急处理' },
  { id: 'relatedAttachment__c', name: '相关附件', group: 'description', type: 'text', originalValue: '故障照片.pdf, 维修记录.docx' },
  { id: 'feedbackChannel__c', name: '反馈渠道', group: 'description', type: 'select', originalValue: '1', required: true, options: [
    { label: '400电话-1', value: '1' }, { label: '企微助手-2', value: '2' },
    { label: '微信客服-3', value: '3' }, { label: '邮件-7', value: '7' },
  ]},

  // ---- 反馈信息 (feedback) ----
  { id: 'feedbackUserName__c', name: '反馈人姓名', group: 'feedback', type: 'text', originalValue: '佐藤健' },
  { id: 'feedbackUserContact__c', name: '反馈人联系方式', group: 'feedback', type: 'phone', originalValue: '13800138000' },
  { id: 'feedbackCount__c', name: '反馈次数', group: 'feedback', type: 'text', originalValue: '3' },
  { id: 'needCallBack__c', name: '是否要求回电话', group: 'feedback', type: 'select', originalValue: '1', options: [
    { label: '是-1', value: '1' }, { label: '否-2', value: '2' },
  ]},

  // ---- 处理信息 (handling) ----
  { id: 'problemResponsible__c', name: '问题责任人', group: 'handling', type: 'text', originalValue: 'EMP000456', required: true },
  { id: 'problemDept__c', name: '问题责任部门', group: 'handling', type: 'text', originalValue: 'DEPT003' },
  { id: 'isHandled__c', name: '是否处理', group: 'handling', type: 'select', originalValue: '2', options: [
    { label: '是-1', value: '1' }, { label: '否-2', value: '2' },
  ]},
  { id: 'needOnSite__c', name: '是否要求进场', group: 'handling', type: 'select', originalValue: '1', options: [
    { label: '是-1', value: '1' }, { label: '否-2', value: '2' },
  ]},
  { id: 'planFeedbackTime__c', name: '方案反馈时间（默认）', group: 'handling', type: 'datetime', originalValue: '1784797500' },
  { id: 'requireSolveTime__c', name: '要求解决时间', group: 'handling', type: 'datetime', originalValue: '1784883900' },

  // ---- 系统信息 (system) ----
  { id: 'serial_number', name: '工单编号', group: 'system', type: 'text', originalValue: 'WO-20260717-0381', readonly: true },
  { id: 'version', name: '数据版本', group: 'system', type: 'number', originalValue: 2, readonly: true },
  { id: 'status', name: '审核状态', group: 'system', type: 'text', originalValue: 'pending_review', readonly: true },
  { id: 'reject_count', name: '驳回次数', group: 'system', type: 'number', originalValue: 0, readonly: true },
  { id: 'last_reject_reason', name: '上次驳回原因', group: 'system', type: 'textarea', originalValue: '', readonly: true },
  { id: 'last_rejected_by', name: '上次驳回人', group: 'system', type: 'text', originalValue: '', readonly: true },
  { id: 'last_rejected_at', name: '上次驳回时间', group: 'system', type: 'datetime', originalValue: '', readonly: true },
];

/** 异常模板 */
export const ANOMALY_TEMPLATE: Anomaly[] = [
  { id: 'a1', type: 'blocking_error', fieldId: 'bigCustShortName__c', message: '大客户简称未填写（必填字段）' },
  { id: 'a2', type: 'warning', fieldId: 'problemLevel__c', message: '问题等级为"重要紧急"，描述为"完全停机"，等级与描述一致需关注' },
  { id: 'a3', type: 'warning', fieldId: 'projectProvince__c', message: '项目省份数据异常，请重点审核' },
  { id: 'a4', type: 'warning', fieldId: 'workOrderStatus__c', message: '工单类型发生过规则覆盖（系统覆盖为"售后单"）' },
  { id: 'a5', type: 'info', fieldId: 'feedbackChannel__c', message: '来源为400电话，建议核实现场情况' },
  { id: 'a6', type: 'system_suggestion', fieldId: 'problemType3__c', message: '建议问题分类-3级使用"系统 BUG-6"' },
];

/** 审计时间线模板 */
export const AUDIT_TEMPLATE: AuditLogEntry[] = [
  { id: 'l1', timestamp: '2026-07-17T10:42:00', category: 'system', actor: '监控告警平台', action: '系统自动生成工单', detail: '告警 #A-9981 触发' },
  { id: 'l3', timestamp: '2026-07-17T10:43:00', category: 'external', actor: '系统', action: '工单类型规则覆盖', detail: '自动分类为「售后单」' },
  { id: 'l4', timestamp: '2026-07-17T10:44:00', category: 'process', actor: '李四', action: '转交至 张三', detail: '二线转单' },
  { id: 'l5', timestamp: '2026-07-17T10:45:00', category: 'process', actor: '张三', action: '开始审核' },
  { id: 'l6', timestamp: '2026-07-17T10:46:00', category: 'field_change', actor: '张三', action: '修改「工单类型」', detail: '1 → 5' },
  { id: 'l7', timestamp: '2026-07-17T10:48:00', category: 'field_change', actor: '张三', action: '修改「项目省份」', detail: '广东 → 浙江' },
];

/** 主工单预置修改 */
export const PRESEEDED: Record<string, { currentValue: unknown; reason: string; changedAt: string }> = {
  workOrderStatus__c: { currentValue: '5', reason: 'rule_mismatch', changedAt: '2026-07-17T10:46:00' },
  projectProvince__c: { currentValue: '浙江', reason: 'system_error', changedAt: '2026-07-17T10:48:00' },
};

/** 主工单 ID */
export const MAIN_TICKET_ID = 'wo-0381';

/** 队列 */
export const QUEUE: QueueItem[] = [
  {
    id: 'wo-0381', serialNumber: 'WO-20260717-0381', title: '东京二区设备故障报修', type: '售后单', source: '400电话',
    status: 'pending_review', anomalyCount: 6, slaRemainingMin: 36,
    createdAt: '2026-07-17T10:42:00', modified: true, urgency: 'high', hasValidationError: true,
  },
  {
    id: 'wo-0379', serialNumber: 'WO-20260717-0379', title: '网络链路中断报修', type: '投诉单', source: '微信客服',
    status: 'pending_review', anomalyCount: 4, slaRemainingMin: 12,
    createdAt: '2026-07-17T10:30:00', urgency: 'high', hasValidationError: true,
  },
  {
    id: 'wo-0377', serialNumber: 'WO-20260717-0377', title: '制冷系统报警处理', type: '售后单', source: '企微助手',
    status: 'pending_review', anomalyCount: 3, slaRemainingMin: 95,
    createdAt: '2026-07-17T09:55:00', urgency: 'medium',
  },
  {
    id: 'wo-0375', serialNumber: 'WO-20260717-0375', title: '门禁异常巡检', type: '售后单', source: '巡检',
    status: 'returned', anomalyCount: 2, slaRemainingMin: 200,
    createdAt: '2026-07-17T09:20:00', urgency: 'low',
  },
  {
    id: 'wo-0372', serialNumber: 'WO-20260717-0372', title: '巡检发现异响问题', type: '巡检单', source: '巡检',
    status: 'pending_review', anomalyCount: 1, slaRemainingMin: 150,
    createdAt: '2026-07-17T08:40:00', urgency: 'medium', hasValidationError: true,
  },
  {
    id: 'wo-0369', serialNumber: 'WO-20260717-0369', title: 'UPS 电池告警处理', type: 'A类售后单', source: '工程运维部',
    status: 'pending_review', anomalyCount: 5, slaRemainingMin: 28,
    createdAt: '2026-07-17T08:10:00', urgency: 'high', lockedByOther: '李四',
  },
  {
    id: 'wo-0365', serialNumber: 'WO-20260717-0365', title: '监控摄像头离线', type: '售后单', source: '邮件',
    status: 'stashed', anomalyCount: 2, slaRemainingMin: 300,
    createdAt: '2026-07-17T07:50:00', urgency: 'low', stashed: true,
  },
  {
    id: 'wo-0361', serialNumber: 'WO-20260717-0361', title: '空调不制冷报修', type: '售后单', source: '销售部',
    status: 'pending_review', anomalyCount: 0, slaRemainingMin: 240,
    createdAt: '2026-07-17T07:10:00', urgency: 'medium',
  },
];

/** 版本冲突演示数据 */
export const CONFLICT_DEMO = {
  otherUser: '李四',
  theirVersion: 3,
  theirChanges: [{ fieldName: '问题等级', before: '1', after: '2' }],
};

function pickAnomalies(count: number): Anomaly[] {
  if (count <= 0) return [];
  return ANOMALY_TEMPLATE.slice(0, Math.min(count, ANOMALY_TEMPLATE.length));
}

/** 根据队列项构建完整工单 */
export function buildTicket(item: QueueItem): ReviewTicket {
  const isMain = item.id === MAIN_TICKET_ID;
  const fields = FIELD_TEMPLATE.map((f) => ({
    ...f,
    ...(f.id === 'serial_number' ? { originalValue: item.serialNumber } : {}),
    ...(f.id === 'name' ? { originalValue: item.title } : {}),
    ...(f.id === 'workOrderStatus__c' ? { originalValue: isMain ? '1' : '1' } : {}),
    ...(f.id === 'created_at' ? { originalValue: item.createdAt } : {}),
    ...(f.id === 'feedbackChannel__c' ? { originalValue: '1' } : {}),
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
