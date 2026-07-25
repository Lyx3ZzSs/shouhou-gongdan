export interface StatsOverview {
  total_reviewed: number;
  today_reviewed: number;
  avg_duration_seconds: number | null;
  approval_rate: number | null;
  pending_count: number;
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
