import type {
  AnomalyType,
  FieldGroupId,
  FieldReviewStatus,
  ReviewDecision,
  SavedView,
} from '../types';

/** 字段分组（按销售易 serviceCase API 业务逻辑） */
export const FIELD_GROUPS: { id: FieldGroupId; name: string }[] = [
  { id: 'basic', name: '基本信息' },
  { id: 'category', name: '工单分类' },
  { id: 'project', name: '客户与项目' },
  { id: 'service_period', name: '服务周期' },
  { id: 'description', name: '问题描述' },
  { id: 'feedback', name: '反馈信息' },
  { id: 'handling', name: '处理信息' },
  { id: 'system', name: '系统信息' },
];

/** 修改原因选项（spec 第七节） */
export const REVIEW_REASONS: { value: string; label: string }[] = [
  { value: 'system_error', label: '系统识别错误' },
  { value: 'missing_data', label: '原始数据缺失' },
  { value: 'rule_mismatch', label: '业务规则不匹配' },
  { value: 'manual_correction', label: '人工判断修正' },
  { value: 'user_supplement', label: '用户补充信息' },
  { value: 'attachment_fix', label: '附件信息修正' },
  { value: 'adopt_suggestion', label: '采用系统建议值' },
  { value: 'other', label: '其他' },
];

export const REASON_LABEL: Record<string, string> = Object.fromEntries(
  REVIEW_REASONS.map((r) => [r.value, r.label]),
);

/** 审核备注常用短语 */
export const NOTE_PHRASES: string[] = [
  '信息已核实',
  '已根据附件修正',
  '联系人信息待补充',
  '建议二线复核',
  '系统分类存在偏差',
];

/** 字段状态元信息 */
export const STATUS_META: Record<
  FieldReviewStatus,
  { label: string; variant: 'default' | 'success' | 'warning' | 'destructive' | 'muted' | 'outline' }
> = {
  unchecked: { label: '未检查', variant: 'muted' },
  confirmed: { label: '已确认', variant: 'success' },
  modified: { label: '已修改', variant: 'default' },
  warning: { label: '校验异常', variant: 'warning' },
  blocking_error: { label: '阻断错误', variant: 'destructive' },
};

/** 异常类型元信息 */
export const ANOMALY_META: Record<
  AnomalyType,
  { label: string; variant: 'destructive' | 'warning' | 'muted' | 'default' }
> = {
  blocking_error: { label: '阻断错误', variant: 'destructive' },
  warning: { label: '风险提示', variant: 'warning' },
  info: { label: '信息提示', variant: 'muted' },
  system_suggestion: { label: '系统建议', variant: 'default' },
};

/** 审核结论元信息 */
export const DECISION_META: Record<
  ReviewDecision,
  { label: string; variant: 'success' | 'default' | 'warning' | 'destructive' | 'secondary' | 'muted' }
> = {
  approved: { label: '确认通过', variant: 'success' },
  approved_with_changes: { label: '修改后确认', variant: 'default' },
  rejected: { label: '驳回', variant: 'destructive' },
  draft: { label: '暂存', variant: 'muted' },
};

/** 队列状态选项 */
export const QUEUE_STATUS_OPTIONS = [
  { value: 'all', label: '全部状态' },
  { value: 'pending_review', label: '待审核' },
  { value: 'reviewing', label: '审核中' },
  { value: 'returned', label: '已退回' },
  { value: 'stashed', label: '已暂存' },
  { value: 'confirmed', label: '已确认' },
];

export const SLA_OPTIONS = [
  { value: 'all', label: '全部 SLA' },
  { value: 'warning', label: '即将超时' },
  { value: 'timeout', label: '已超时' },
  { value: 'normal', label: '正常' },
];

export const TYPE_OPTIONS = [
  { value: 'all', label: '全部类型' },
  { value: '设备故障', label: '设备故障' },
  { value: '设备异常', label: '设备异常' },
  { value: '网络异常', label: '网络异常' },
  { value: '巡检任务', label: '巡检任务' },
];

export const SOURCE_OPTIONS = [
  { value: 'all', label: '全部来源' },
  { value: '监控告警自动生成', label: '监控告警自动生成' },
  { value: '用户报修', label: '用户报修' },
  { value: '巡检上报', label: '巡检上报' },
  { value: '二线转单', label: '二线转单' },
];

/** 预置保存视图（spec 第三节） */
export const DEFAULT_SAVED_VIEWS: SavedView[] = [
  { id: 'mine', name: '我的待审核', filters: { status: 'pending_review' } },
  { id: 'near_timeout', name: '即将超时', filters: { sla: 'warning' } },
  { id: 'returned', name: '退回后重新提交', filters: { status: 'returned' } },
];
