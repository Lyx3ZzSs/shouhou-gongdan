import type {
  Anomaly,
  AuditLogEntry,
  FieldDef,
  QueueItem,
  ReviewTicket,
} from '../types';

/** 字段模板（24 个字段，跨 8 个分组；originalValue 为系统原始值） */
export const FIELD_TEMPLATE: FieldDef[] = [
  // 基本信息
  { id: 'serial', name: '工单编号', group: 'basic', type: 'text', originalValue: 'WO-20260717-0381', readonly: true },
  { id: 'title', name: '工单标题', group: 'basic', type: 'text', originalValue: '设备故障报修', isKey: true },
  {
    id: 'type', name: '工单类型', group: 'basic', type: 'select', originalValue: '设备异常', isKey: true,
    options: [
      { label: '设备故障', value: '设备故障' },
      { label: '设备异常', value: '设备异常' },
      { label: '网络异常', value: '网络异常' },
      { label: '巡检任务', value: '巡检任务' },
    ],
  },
  {
    id: 'urgency', name: '紧急程度', group: 'basic', type: 'select', originalValue: '中', isKey: true,
    options: [{ label: '高', value: '高' }, { label: '中', value: '中' }, { label: '低', value: '低' }],
  },
  {
    id: 'riskLevel', name: '风险等级', group: 'basic', type: 'select', originalValue: 'high',
    options: [{ label: '高风险', value: 'high' }, { label: '中风险', value: 'medium' }, { label: '低风险', value: 'low' }],
  },
  {
    id: 'source', name: '来源渠道', group: 'basic', type: 'select', originalValue: '监控告警自动生成',
    options: [
      { label: '监控告警自动生成', value: '监控告警自动生成' },
      { label: '用户报修', value: '用户报修' },
      { label: '巡检上报', value: '巡检上报' },
      { label: '二线转单', value: '二线转单' },
    ],
  },
  // 联系人与服务对象
  { id: 'contactName', name: '联系人', group: 'contact', type: 'text', originalValue: '佐藤健', isKey: true },
  { id: 'contactPhone', name: '联系电话', group: 'contact', type: 'phone', originalValue: '', required: true, isKey: true },
  { id: 'serviceTarget', name: '服务对象', group: 'contact', type: 'text', originalValue: '东京二区 7-11 便利店（新宿店）' },
  // 问题描述
  { id: 'faultDesc', name: '故障描述', group: 'description', type: 'textarea', originalValue: '设备完全停机，无法运行，现场有焦糊味。', isKey: true },
  {
    id: 'faultLevel', name: '故障等级', group: 'description', type: 'select', originalValue: '低',
    options: [{ label: '高', value: '高' }, { label: '中', value: '中' }, { label: '低', value: '低' }],
  },
  { id: 'deviceName', name: '设备名称', group: 'description', type: 'text', originalValue: '未知', systemSuggestion: 'XYZ-2000 变频器', confidence: 70 },
  { id: 'deviceCode', name: '设备编号', group: 'description', type: 'text', originalValue: 'SN-2024-009812' },
  // 分类与优先级
  {
    id: 'categoryL1', name: '问题分类(L1)', group: 'category', type: 'select', originalValue: '设备类',
    options: [{ label: '设备类', value: '设备类' }, { label: '网络类', value: '网络类' }, { label: '环境类', value: '环境类' }],
  },
  {
    id: 'categoryL2', name: '问题分类(L2)', group: 'category', type: 'select', originalValue: '变频器',
    options: [{ label: '变频器', value: '变频器' }, { label: 'UPS', value: 'UPS' }, { label: '空调', value: '空调' }],
  },
  {
    id: 'priority', name: '处理优先级', group: 'category', type: 'select', originalValue: 'P1', isKey: true,
    options: [{ label: 'P0', value: 'P0' }, { label: 'P1', value: 'P1' }, { label: 'P2', value: 'P2' }, { label: 'P3', value: 'P3' }],
  },
  // 地址与区域
  {
    id: 'region', name: '所属区域', group: 'address', type: 'select', originalValue: '东京二区', confidence: 43, isKey: true,
    options: [
      { label: '东京一区', value: '东京一区' },
      { label: '东京二区', value: '东京二区' },
      { label: '东京三区', value: '东京三区' },
      { label: '大阪区', value: '大阪区' },
    ],
  },
  { id: 'address', name: '详细地址', group: 'address', type: 'text', originalValue: '东京二区新宿区西新宿2-8-1' },
  // 处理要求
  { id: 'handleReq', name: '处理要求', group: 'requirement', type: 'textarea', originalValue: '请尽快上门检修，恢复设备运行。' },
  { id: 'expectResolve', name: '期望解决时间', group: 'requirement', type: 'datetime', originalValue: '2026-07-17T18:00:00' },
  { id: 'sla', name: 'SLA', group: 'requirement', type: 'text', originalValue: '4 小时', readonly: true },
  // 附件与证据
  { id: 'attachments', name: '附件', group: 'attachment', type: 'tags', originalValue: ['现场照片.jpg', '设备铭牌.jpg'] },
  // 系统生成信息
  { id: 'createdAt', name: '创建时间', group: 'system', type: 'datetime', originalValue: '2026-07-17T10:42:00', readonly: true },
  { id: 'systemConfidence', name: '系统置信度', group: 'system', type: 'text', originalValue: '72%', readonly: true },
  { id: 'sourceSystem', name: '来源系统', group: 'system', type: 'text', originalValue: '监控告警平台', readonly: true },
  { id: 'aiBasis', name: '系统生成依据', group: 'system', type: 'textarea', originalValue: '根据监控告警 #A-9981 自动生成，识别设备停机信号并匹配工单模板。', readonly: true },
  { id: 'reviewer', name: '当前审核人', group: 'system', type: 'text', originalValue: '张三', readonly: true },
];

/** 异常模板（6 条：1 阻断 / 3 风险 / 1 信息 / 1 系统建议） */
export const ANOMALY_TEMPLATE: Anomaly[] = [
  { id: 'a1', type: 'blocking_error', fieldId: 'contactPhone', message: '联系电话缺失（必填字段未填写）' },
  { id: 'a2', type: 'warning', fieldId: 'faultLevel', message: '故障等级与故障描述不一致：描述为"完全停机"但等级为"低"' },
  { id: 'a3', type: 'warning', fieldId: 'region', message: '所属区域置信度仅 43%' },
  { id: 'a4', type: 'warning', fieldId: 'type', message: '工单类型发生过规则覆盖（系统覆盖为"设备异常"）' },
  { id: 'a5', type: 'info', fieldId: 'source', message: '来源为监控告警自动生成，建议核实现场情况' },
  { id: 'a6', type: 'system_suggestion', fieldId: 'deviceName', message: '建议设备名称使用"XYZ-2000 变频器"' },
];

/** 审计时间线模板（7 条，覆盖 system/external/process/field_change） */
export const AUDIT_TEMPLATE: AuditLogEntry[] = [
  { id: 'l1', timestamp: '2026-07-17T10:42:00', category: 'system', actor: '监控告警平台', action: '系统自动生成工单', detail: '告警 #A-9981 触发' },
  { id: 'l2', timestamp: '2026-07-17T10:42:01', category: 'system', actor: '系统', action: '字段置信度计算完成', detail: '整体置信度 72%' },
  { id: 'l3', timestamp: '2026-07-17T10:43:00', category: 'external', actor: '系统', action: '工单类型规则覆盖', detail: '自动分类为「设备异常」' },
  { id: 'l4', timestamp: '2026-07-17T10:44:00', category: 'process', actor: '李四', action: '转交至 张三', detail: '二线转单' },
  { id: 'l5', timestamp: '2026-07-17T10:45:00', category: 'process', actor: '张三', action: '开始审核' },
  { id: 'l6', timestamp: '2026-07-17T10:46:00', category: 'field_change', actor: '张三', action: '修改「工单类型」', detail: '设备异常 → 设备故障' },
  { id: 'l7', timestamp: '2026-07-17T10:48:00', category: 'field_change', actor: '张三', action: '修改「所属区域」', detail: '东京二区 → 东京一区' },
];

/** 主工单预置修改（演示"已产生多项人工修改"状态） */
export const PRESEEDED: Record<string, { currentValue: unknown; reason: string; changedAt: string }> = {
  type: { currentValue: '设备故障', reason: 'rule_mismatch', changedAt: '2026-07-17T10:46:00' },
  region: { currentValue: '东京一区', reason: 'system_error', changedAt: '2026-07-17T10:48:00' },
};

/** 主工单 ID */
export const MAIN_TICKET_ID = 'wo-0381';

/** 队列（8 条，覆盖不同状态/风险/SLA/异常/暂存/被编辑） */
export const QUEUE: QueueItem[] = [
  {
    id: 'wo-0381', serialNumber: 'WO-20260717-0381', title: '设备故障报修', type: '设备故障',
    riskLevel: 'high', status: 'pending_review', anomalyCount: 6, slaRemainingMin: 36,
    createdAt: '2026-07-17T10:42:00', modified: true, urgency: 'medium', hasLowConfidence: true, hasValidationError: true,
  },
  {
    id: 'wo-0379', serialNumber: 'WO-20260717-0379', title: '网络链路中断', type: '网络异常',
    riskLevel: 'high', status: 'pending_review', anomalyCount: 4, slaRemainingMin: 12,
    createdAt: '2026-07-17T10:30:00', urgency: 'high', hasValidationError: true,
  },
  {
    id: 'wo-0377', serialNumber: 'WO-20260717-0377', title: '制冷系统报警', type: '设备故障',
    riskLevel: 'medium', status: 'pending_review', anomalyCount: 3, slaRemainingMin: 95,
    createdAt: '2026-07-17T09:55:00', urgency: 'medium', hasLowConfidence: true,
  },
  {
    id: 'wo-0375', serialNumber: 'WO-20260717-0375', title: '门禁异常', type: '设备异常',
    riskLevel: 'low', status: 'returned', anomalyCount: 2, slaRemainingMin: 200,
    createdAt: '2026-07-17T09:20:00', urgency: 'low',
  },
  {
    id: 'wo-0372', serialNumber: 'WO-20260717-0372', title: '巡检发现异响', type: '巡检任务',
    riskLevel: 'medium', status: 'pending_review', anomalyCount: 1, slaRemainingMin: 150,
    createdAt: '2026-07-17T08:40:00', urgency: 'medium', hasValidationError: true,
  },
  {
    id: 'wo-0369', serialNumber: 'WO-20260717-0369', title: 'UPS 电池告警', type: '设备故障',
    riskLevel: 'high', status: 'pending_review', anomalyCount: 5, slaRemainingMin: 28,
    createdAt: '2026-07-17T08:10:00', urgency: 'high', lockedByOther: '李四', hasLowConfidence: true,
  },
  {
    id: 'wo-0365', serialNumber: 'WO-20260717-0365', title: '监控摄像头离线', type: '设备异常',
    riskLevel: 'low', status: 'stashed', anomalyCount: 2, slaRemainingMin: 300,
    createdAt: '2026-07-17T07:50:00', urgency: 'low', stashed: true,
  },
  {
    id: 'wo-0361', serialNumber: 'WO-20260717-0361', title: '空调不制冷', type: '设备故障',
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
    // 非主工单：编号/创建时间等用队列项信息覆盖，保持模板字段结构
    ...(f.id === 'serial' ? { originalValue: item.serialNumber } : {}),
    ...(f.id === 'title' ? { originalValue: item.title } : {}),
    ...(f.id === 'type' ? { originalValue: isMain ? '设备异常' : item.type } : {}),
    ...(f.id === 'riskLevel' ? { originalValue: item.riskLevel } : {}),
    ...(f.id === 'createdAt' ? { originalValue: item.createdAt } : {}),
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
    source: isMain ? '监控告警自动生成' : '监控告警自动生成',
    status: item.status === 'stashed' ? 'pending_review' : item.status,
    createdAt: item.createdAt,
    slaRemainingMin: item.slaRemainingMin,
    systemConfidence: isMain ? 72 : 68,
    reviewer: '张三',
    version: isMain ? 2 : 1,
    fields,
    anomalies,
    auditLogs,
  };
}
