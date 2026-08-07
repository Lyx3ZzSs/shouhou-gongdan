import type {
  StatsOverview,
  ReviewerStat,
  TrendPoint,
  DurationBucket,
  StatusBucket,
  FieldCorrection,
  EfficiencyPoint,
} from '../stats/types';
import { authFetch } from './review';

const BASE = '/api/stats';

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await authFetch(url);
  if (!res.ok) throw new Error(`请求失败: ${res.status}`);
  return res.json();
}

export async function fetchStatsOverview(): Promise<StatsOverview> {
  return fetchJSON(`${BASE}/overview`);
}

export async function fetchByReviewer(
  from?: string,
  to?: string,
): Promise<ReviewerStat[]> {
  const params = new URLSearchParams();
  if (from) params.set('from', from);
  if (to) params.set('to', to);
  return fetchJSON(`${BASE}/by-reviewer?${params}`);
}

export async function fetchTrends(days = 30): Promise<TrendPoint[]> {
  return fetchJSON(`${BASE}/trends?days=${days}`);
}

export async function fetchDurationDistribution(): Promise<DurationBucket[]> {
  return fetchJSON(`${BASE}/duration-distribution`);
}

export async function fetchStatusDistribution(): Promise<StatusBucket[]> {
  return fetchJSON(`${BASE}/status-distribution`);
}

/** 错误字段聚合：按字段统计修正频次 */
export async function fetchFieldCorrections(limit = 20): Promise<FieldCorrection[]> {
  return fetchJSON(`${BASE}/field-corrections?limit=${limit}`);
}

/** 售后效率趋势：按周聚合一次通过率/返工/修正/同步接受率 */
export async function fetchEfficiency(weeks = 12): Promise<EfficiencyPoint[]> {
  return fetchJSON(`${BASE}/efficiency?weeks=${weeks}`);
}
