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
import type { FieldChange } from '../../types/review';
import { getCurrentUserName } from '../../auth/parseUser';

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

// ---- 销售易 serviceCase API 枚举选项 ----

const CASE_SOURCE_OPTIONS = [
  { label: '语音-1', value: '1' },
  { label: '小组件-2', value: '2' },
  { label: '留言-3', value: '3' },
  { label: '意见反馈-4', value: '4' },
  { label: '其他-5', value: '5' },
  { label: '微信公众号-6', value: '6' },
  { label: '邮件-7', value: '7' },
  { label: 'APP-8', value: '8' },
  { label: '微博-9', value: '9' },
  { label: '微信小程序-99', value: '99' },
];

const FEEDBACK_CHANNEL_OPTIONS = [
  { label: '400电话-1', value: '1' },
  { label: '企微助手-2', value: '2' },
  { label: '微信客服-3', value: '3' },
  { label: '销售部-4', value: '4' },
  { label: '企微群-5', value: '5' },
  { label: '微信-6', value: '6' },
  { label: '邮件-7', value: '7' },
  { label: '客户会议-8', value: '8' },
  { label: '大客戶群-9', value: '9' },
  { label: '闭环回访-10', value: '10' },
  { label: '日常回访-11', value: '11' },
  { label: '工程运维部-12', value: '12' },
  { label: '数据中心-13', value: '13' },
  { label: '产品部-14', value: '14' },
  { label: '售后服务部-15', value: '15' },
  { label: '巡检-16', value: '16' },
  { label: '精度会议-17', value: '17' },
  { label: '替换会议-18', value: '18' },
];

const WORK_ORDER_STATUS_OPTIONS = [
  { label: '售后单-1', value: '1' },
  { label: '投诉单-2', value: '2' },
  { label: 'A类售后单-3', value: '3' },
  { label: '提级售后单-4', value: '4' },
  { label: '大客户售后单-5', value: '5' },
  { label: '重要受理单-6', value: '6' },
  { label: '非常重要受理单-7', value: '7' },
  { label: '定期报告跟蹤-8', value: '8' },
  { label: '定期巡检跟踪-9', value: '9' },
  { label: '多项目售后单-10', value: '10' },
  { label: '影响回款项目-11', value: '11' },
  { label: '替换项目跟踪-12', value: '12' },
  { label: '专项整改-13', value: '13' },
];

const CASE_STATUS_OPTIONS = [
  { label: '待分配-1', value: '1' },
  { label: '待处理-2', value: '2' },
  { label: '处理中-3', value: '3' },
  { label: '待确认-4', value: '4' },
  { label: '已完成-5', value: '5' },
  { label: '待回访-6', value: '6' },
];

const YES_NO_OPTIONS = [
  { label: '是-1', value: '1' },
  { label: '否-2', value: '2' },
];

const PROBLEM_LEVEL_OPTIONS = [
  { label: '常规问题-1', value: '1' },
  { label: '重要紧急-2', value: '2' },
];

const PROBLEM_TYPE1_OPTIONS = [
  { label: '现场问题-1', value: '1' },
  { label: '数据优化-2', value: '2' },
  { label: '报告/回函-3', value: '3' },
  { label: '技术交流-4', value: '4' },
  { label: '多部门处理-5', value: '5' },
  { label: '其他-6', value: '6' },
];

const PROBLEM_TYPE2_OPTIONS = [
  { label: '系统问题-1', value: '1' },
  { label: '硬件故障 / 更换-2', value: '2' },
  { label: '二次安防-3', value: '3' },
  { label: '调试 / 安装-4', value: '4' },
  { label: '数据采集-5', value: '5' },
  { label: '倒塔问题-6', value: '6' },
  { label: 'AGC 拉停-7', value: '7' },
  { label: '运维问题-8', value: '8' },
  { label: 'AGC 考核分析-9', value: '9' },
  { label: '版本低需升级-10', value: '10' },
  { label: '试验-11', value: '11' },
  { label: '调度联调 / 并网-12', value: '12' },
  { label: '其他-13', value: '13' },
  { label: '理论功率-14', value: '14' },
  { label: '预测调整-15', value: '15' },
  { label: '扩容 / 减容-16', value: '16' },
  { label: '精度问题-17', value: '17' },
  { label: '数据跳变-18', value: '18' },
  { label: '考核报告-19', value: '19' },
  { label: '服务报告-20', value: '20' },
  { label: '故障报告-21', value: '21' },
  { label: 'PK / 对比分析报告-22', value: '22' },
  { label: '数据 / 资料收集-23', value: '23' },
  { label: '来函回函-24', value: '24' },
  { label: '说明函-25', value: '25' },
  { label: '技术交流 -- 线上-26', value: '26' },
  { label: '技术交流 -- 线下-27', value: '27' },
  { label: '电话咨询 / 答疑-28', value: '28' },
  { label: '培训-29', value: '29' },
  { label: '线上 - 单部门-30', value: '30' },
  { label: '线下 - 单部门-31', value: '31' },
  { label: '线上 - 多部门-32', value: '32' },
  { label: '线下 - 多部门-33', value: '33' },
  { label: '报告 / 回函（多部门）-34', value: '34' },
  { label: '扩容 / 减容（多部门）-35', value: '35' },
  { label: '技术交流（多部门）-36', value: '36' },
  { label: '表格填写（多部门）-37', value: '37' },
  { label: '可用功率（多部门）-38', value: '38' },
  { label: '商机（线索）-39', value: '39' },
  { label: '新需求-40', value: '40' },
  { label: '规则核对-41', value: '41' },
  { label: '空值-42', value: '42' },
];

const PROBLEM_TYPE3_OPTIONS = [
  { label: '系统界面问题-1', value: '1' },
  { label: '通讯问题-2', value: '2' },
  { label: '程序问题-3', value: '3' },
  { label: '数据治理-4', value: '4' },
  { label: '配置问题-5', value: '5' },
  { label: '系统 BUG-6', value: '6' },
  { label: '保期内（维修、补采）-7', value: '7' },
  { label: '保期外-8', value: '8' },
  { label: '非我司设备-9', value: '9' },
  { label: '软件问题-10', value: '10' },
  { label: '硬件问题-11', value: '11' },
  { label: '设备及系统安装调试-12', value: '12' },
  { label: '巡检-13', value: '13' },
  { label: '消缺问题-14', value: '14' },
  { label: '升级改造-15', value: '15' },
  { label: '设备试验-16', value: '16' },
  { label: '配合第三方数据上传-17', value: '17' },
  { label: '储能数据未剔除-18', value: '18' },
  { label: '现场数据采集异常-19', value: '19' },
  { label: 'FTP 账号-20', value: '20' },
  { label: '数据补传-21', value: '21' },
  { label: '数据合格率考核-22', value: '22' },
  { label: '设备质量问题-23', value: '23' },
  { label: '非我司问题-24', value: '24' },
  { label: '软硬件设备问题-25', value: '25' },
  { label: '非我司-26', value: '26' },
  { label: '工程师配置错误-27', value: '27' },
  { label: '合格率、变化率-28', value: '28' },
  { label: '空-29', value: '29' },
  { label: '涉网试验-30', value: '30' },
  { label: '电科院试验-31', value: '31' },
  { label: '调度联调-32', value: '32' },
  { label: '调度对点-33', value: '33' },
  { label: '并网调试-34', value: '34' },
  { label: '无-35', value: '35' },
  { label: '逻辑不符-36', value: '36' },
  { label: '样本机跟随实发-37', value: '37' },
  { label: '系数调整-38', value: '38' },
  { label: '场站个性化需求调整-39', value: '39' },
  { label: '失电-40', value: '40' },
  { label: '限电跟随-41', value: '41' },
  { label: '偏差不合格-42', value: '42' },
  { label: '数据跳变-43', value: '43' },
  { label: '扩容-44', value: '44' },
  { label: '减容-45', value: '45' },
  { label: '短期 / 超短期 / 中期-46', value: '46' },
  { label: '偏差问题（最大误差、相关性系数）-47', value: '47' },
  { label: '精度报告-48', value: '48' },
  { label: '免考报告-49', value: '49' },
  { label: 'AGC 报告-50', value: '50' },
  { label: '数据治理报告-51', value: '51' },
  { label: '月报（1-2 个月）-52', value: '52' },
  { label: '季报（3-11 个月）-53', value: '53' },
  { label: '年报-54', value: '54' },
  { label: '调试报告-55', value: '55' },
  { label: '个性化报告-56', value: '56' },
  { label: '验收报告-57', value: '57' },
  { label: '非我司（系统及设备）问题-58', value: '58' },
  { label: '我司维护期内-59', value: '59' },
  { label: '已出质保-60', value: '60' },
  { label: 'PK / 对比分析报告-61', value: '61' },
  { label: '软硬件资料（查询品牌参数）-62', value: '62' },
  { label: '气象站资料-63', value: '63' },
  { label: '历史数据导出-64', value: '64' },
  { label: '软硬件问题回函-65', value: '65' },
  { label: '考核问题-66', value: '66' },
  { label: '响应问题-67', value: '67' },
  { label: '模型优化问题-68', value: '68' },
  { label: '当日-69', value: '69' },
  { label: '3 日以上-70', value: '70' },
  { label: '次日-71', value: '71' },
  { label: '入场-72', value: '72' },
  { label: '非入场-73', value: '73' },
  { label: '3 日及以上-74', value: '74' },
  { label: '服务报告-75', value: '75' },
  { label: '故障 / 考核报告-76', value: '76' },
  { label: '回函-77', value: '77' },
  { label: '资料收集-78', value: '78' },
  { label: '扩容、减容-79', value: '79' },
  { label: '线上-80', value: '80' },
  { label: '线下-81', value: '81' },
  { label: '表格填写-82', value: '82' },
  { label: '理论功率-83', value: '83' },
  { label: '咨询 / 购买产品-84', value: '84' },
  { label: '谈合作-85', value: '85' },
  { label: '区域性问题-86', value: '86' },
  { label: '其他-87', value: '87' },
  { label: '规则核对-88', value: '88' },
  { label: '空值-89', value: '89' },
];

const FIELD_MAPPING: FieldMapping[] = [
  // ---- 基本信息 (basic) ----
  { backendKey: 'ownerId', id: 'ownerId', name: '所有人', group: 'basic', type: 'text', required: true },
  { backendKey: 'dimDepart', id: 'dimDepart', name: '所属部门', group: 'basic', type: 'text', required: true },
  { backendKey: 'entityType', id: 'entityType', name: '业务类型', group: 'basic', type: 'text', readonly: true },
  { backendKey: 'name', id: 'name', name: '工单主题', group: 'basic', type: 'text', required: true, isKey: true },
  { backendKey: 'caseStatus', id: 'caseStatus', name: '工单状态', group: 'basic', type: 'select', required: true, options: CASE_STATUS_OPTIONS },
  { backendKey: 'created_at', id: 'created_at', name: '创建时间', group: 'basic', type: 'datetime', readonly: true },

  // ---- 工单分类 (category) ----
  { backendKey: 'caseSource', id: 'caseSource', name: '工单来源', group: 'category', type: 'select', required: true, options: CASE_SOURCE_OPTIONS },
  { backendKey: 'workOrderStatus__c', id: 'workOrderStatus__c', name: '工单类型', group: 'category', type: 'select', required: true, options: WORK_ORDER_STATUS_OPTIONS },
  { backendKey: 'problemLevel__c', id: 'problemLevel__c', name: '问题等级', group: 'category', type: 'select', options: PROBLEM_LEVEL_OPTIONS },
  { backendKey: 'problemType1__c', id: 'problemType1__c', name: '问题分类-1级', group: 'category', type: 'select', options: PROBLEM_TYPE1_OPTIONS },
  { backendKey: 'problemType2__c', id: 'problemType2__c', name: '问题分类-2级', group: 'category', type: 'select', options: PROBLEM_TYPE2_OPTIONS },
  { backendKey: 'problemType3__c', id: 'problemType3__c', name: '问题分类-3级', group: 'category', type: 'select', options: PROBLEM_TYPE3_OPTIONS },

  // ---- 客户与项目 (project) ----
  { backendKey: 'bigCustShortName__c', id: 'bigCustShortName__c', name: '大客户简称', group: 'project', type: 'text' },
  { backendKey: 'custLevel1__c', id: 'custLevel1__c', name: '客户级别', group: 'project', type: 'text' },
  { backendKey: 'projectName__c', id: 'projectName__c', name: '项目名称', group: 'project', type: 'text', required: true, isKey: true },
  { backendKey: 'projectProvince__c', id: 'projectProvince__c', name: '项目省份', group: 'project', type: 'text' },
  { backendKey: 'caseAccountId', id: 'caseAccountId', name: '场站编号', group: 'project', type: 'text', required: true, isKey: true },
  { backendKey: 'stationName', id: 'stationName', name: '场站名称', group: 'project', type: 'text', readonly: true },

  // ---- 服务周期 (service_period) ----
  { backendKey: 'serviceCycleStart__c', id: 'serviceCycleStart__c', name: '周期服务开始时间', group: 'service_period', type: 'datetime' },
  { backendKey: 'serviceCycleEnd__c', id: 'serviceCycleEnd__c', name: '周期服务结束时间', group: 'service_period', type: 'datetime' },
  { backendKey: 'isOfflineApply__c', id: 'isOfflineApply__c', name: '是否线下申请', group: 'service_period', type: 'select', options: YES_NO_OPTIONS },
  { backendKey: 'isOverdueService__c', id: 'isOverdueService__c', name: '是否超期服务', group: 'service_period', type: 'select', options: YES_NO_OPTIONS },

  // ---- 问题描述 (description) ----
  { backendKey: 'caseDescription', id: 'caseDescription', name: '工单描述', group: 'description', type: 'textarea', isKey: true },
  { backendKey: 'remark__c', id: 'remark__c', name: '备注', group: 'description', type: 'textarea' },
  { backendKey: 'relatedAttachment__c', id: 'relatedAttachment__c', name: '相关附件', group: 'description', type: 'text' },
  { backendKey: 'feedbackChannel__c', id: 'feedbackChannel__c', name: '反馈渠道', group: 'description', type: 'select', required: true, options: FEEDBACK_CHANNEL_OPTIONS },

  // ---- 反馈信息 (feedback) ----
  { backendKey: 'feedbackUserName__c', id: 'feedbackUserName__c', name: '反馈人姓名', group: 'feedback', type: 'text', isKey: true },
  { backendKey: 'feedbackUserContact__c', id: 'feedbackUserContact__c', name: '反馈人联系方式', group: 'feedback', type: 'phone', isKey: true },
  { backendKey: 'feedbackCount__c', id: 'feedbackCount__c', name: '反馈次数', group: 'feedback', type: 'text' },
  { backendKey: 'needCallBack__c', id: 'needCallBack__c', name: '是否要求回电话', group: 'feedback', type: 'select', options: YES_NO_OPTIONS },

  // ---- 处理信息 (handling) ----
  { backendKey: 'problemResponsible__c', id: 'problemResponsible__c', name: '问题责任人', group: 'handling', type: 'text', required: true, isKey: true },
  { backendKey: 'problemDept__c', id: 'problemDept__c', name: '问题责任部门', group: 'handling', type: 'text' },
  { backendKey: 'isHandled__c', id: 'isHandled__c', name: '是否处理', group: 'handling', type: 'select', options: YES_NO_OPTIONS },
  { backendKey: 'needOnSite__c', id: 'needOnSite__c', name: '是否要求进场', group: 'handling', type: 'select', options: YES_NO_OPTIONS },
  { backendKey: 'planFeedbackTime__c', id: 'planFeedbackTime__c', name: '方案反馈时间（默认）', group: 'handling', type: 'datetime' },
  { backendKey: 'requireSolveTime__c', id: 'requireSolveTime__c', name: '要求解决时间', group: 'handling', type: 'datetime' },

  // ---- 系统信息 (system) ----
  { backendKey: 'ticket_id', id: 'ticket_id', name: '工单 ID', group: 'system', type: 'text', readonly: true },
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
  const status = normalizeStatus((summary as Record<string, unknown>).review_status as string);
  return {
    id: summary.id,
    serialNumber: String(summary.ticket_id),
    title: (summary as Record<string, unknown>).name as string
      ?? (summary as Record<string, unknown>).caseAccountId as string
      ?? '未知工单',
    type: '',
    source: '',
    status,
    anomalyCount: 0,
    slaRemainingMin: 480,
    createdAt: summary.created_at ?? new Date().toISOString(),
    urgency: 'medium',
  };
}

function normalizeStatus(s: string | null | undefined): QueueItem['status'] {
  switch (s) {
    case 'pending_review': return 'pending_review';
    case 'reviewing': return 'reviewing';
    case 'returned': return 'returned';
    case 'stashed': return 'stashed';
    case 'confirmed': return 'confirmed';
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
  const dataRec = data as Record<string, unknown>;

  return {
    id: data.id,
    serialNumber: String(data.ticket_id),
    title: (dataRec.name as string)
      ?? (dataRec.projectName__c as string)
      ?? (dataRec.caseAccountId as string)
      ?? '未知工单',
    type: (dataRec.workOrderStatus__c as string) ?? '',
    urgency: deriveUrgency((dataRec.problemLevel__c as string) ?? null),
    source: (dataRec.caseSource as string) ?? '',
    status: normalizeStatus((dataRec.review_status as string) ?? null) as ReviewTicket['status'],
    createdAt: data.created_at ?? new Date().toISOString(),
    slaRemainingMin: computeSlaMinutes((dataRec.requireSolveTime__c as string) ?? null),
    reviewer: getCurrentUserName(),
    version: data.version,
    syncStatus: ((dataRec.sync_status as ReviewTicket['syncStatus']) ?? 'pending'),
    syncExternalId: (dataRec.sync_external_id as string | null) ?? null,
    syncLastError: (dataRec.sync_last_error as string | null) ?? null,
    fields,
    anomalies,
    auditLogs,
  };
}

function buildFieldDefs(data: GeneratedWorkOrderResponse): FieldDef[] {
  const dataRecord = data as Record<string, unknown>;
  const originalData = (dataRecord.original_data ?? {}) as Record<string, unknown>;
  return FIELD_MAPPING.map((m) => {
    const raw = dataRecord[m.backendKey];
    const originalRaw = originalData[m.backendKey];
    const originalValue = originalRaw == null ? (raw == null ? '' : raw) : originalRaw;
    return {
      id: m.id,
      name: m.name,
      group: m.group,
      originalValue,
      currentValue: raw == null ? '' : raw,
      systemSuggestion: undefined,
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
  const validation = dataRecord.validation as {
    issues?: Array<{ code: string; severity: 'blocking' | 'warning' | 'info'; field: string | null; message: string }>;
  } | null | undefined;

  if (validation?.issues) {
    return validation.issues.map((issue, index) => ({
      id: `validation-${index}`,
      code: issue.code,
      type: issue.severity === 'blocking' ? 'blocking_error' : issue.severity,
      fieldId: issue.field ?? undefined,
      message: issue.message,
    }));
  }

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

function deriveUrgency(level: string | null | undefined): 'high' | 'medium' | 'low' {
  if (!level) return 'medium';
  // problemLevel__c: 1=常规问题, 2=重要紧急
  if (level === '2') return 'high';
  return 'medium';
}

function computeSlaMinutes(requireSolveTime: string | null | undefined): number {
  if (!requireSolveTime) return 480;
  const value = requireSolveTime.trim();
  if (!value) return 480;

  let targetMs: number;
  // 纯数字 → 销售易 epoch 秒（如 '1784797500'）
  if (/^\d+$/.test(value)) {
    targetMs = parseInt(value, 10) * 1000;
  } else {
    // 日期字符串：兼容 'YYYY-MM-DD'（视为 UTC 零点，与后端 _normalize_timestamp
    // 的 calendar.timegm 一致）/ 'YYYY-MM-DD HH:MM:SS' / ISO 8601
    const d = value.includes('T') ? new Date(value) : new Date(value.replace(' ', 'T'));
    if (isNaN(d.getTime())) return 480;
    targetMs = d.getTime();
  }

  const remaining = Math.round((targetMs - Date.now()) / 60_000);
  return remaining;
}
