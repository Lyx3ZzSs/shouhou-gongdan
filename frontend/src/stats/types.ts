export interface StatsOverview {
  total_reviewed: number;
  today_reviewed: number;
  avg_duration_seconds: number | null;
  approval_rate: number | null;
  /** 一次通过率：无驳回记录即通过 ÷ 全部通过 */
  one_pass_rate: number | null;
  /** 累计被驳回过（含返工后通过）的工单数 */
  total_rejected: number;
  pending_count: number;
  stashed_count: number;
  sync_failure_count: number;
  rejection_rate: number | null;
  ai_field_modification_rate: number | null;
}

export interface ReviewerStat {
  reviewer_name: string;
  total_reviewed: number;
  approved: number;
  rejected: number;
  avg_duration_seconds: number | null;
}

export interface TrendPoint {
  date: string;
  reviewed_count: number;
  approved_count: number;
  rejected_count: number;
}

export interface DurationBucket {
  range: string;
  count: number;
}

export interface StatusBucket {
  status: string;
  count: number;
}

/** 错误字段聚合：审核中最常修正的字段 */
export interface FieldCorrection {
  field_label: string;
  field_path: string;
  correction_count: number;
}

/** 售后效率趋势：按周聚合，验证审核是否提升售后工单质量 */
export interface EfficiencyPoint {
  /** 周起始日期 YYYY-MM-DD */
  week: string;
  confirmed_count: number;
  /** 一次通过率（%） */
  one_pass_rate: number | null;
  /** 平均返工次数 */
  avg_reject_count: number | null;
  /** 平均修正字段数 */
  avg_corrections: number | null;
  /** 销售易同步接受率（%） */
  sync_acceptance_rate: number | null;
}
