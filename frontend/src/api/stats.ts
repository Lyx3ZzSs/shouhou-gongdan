import type {
  StatsOverview,
  ReviewerStat,
  TrendPoint,
  DurationBucket,
  StatusBucket,
} from '../stats/types';

const BASE = '/api/stats';

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
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
