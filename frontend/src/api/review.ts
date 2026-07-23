import type {
  WorkOrderData, ReviewRequest, ReviewResponse,
  LockStatus,
} from '../types/review';
import type { components } from '../types/api';
import keycloak from '../auth/keycloak';

// ---- Type aliases derived from the generated OpenAPI spec ----
export type GeneratedWorkOrderSummary = components['schemas']['WorkOrderSummary'];
export type GeneratedWorkOrderResponse = components['schemas']['WorkOrderResponse'];
export type GeneratedReviewRequest = components['schemas']['ReviewRequest'];
export type GeneratedReviewResponse = components['schemas']['ReviewResponse'];
export type GeneratedLockStatus = components['schemas']['LockStatus'];
export type GeneratedAuditLogEntry = components['schemas']['AuditLogEntry'];

const BASE = '/api/workorders';

function getToken(): string {
  return keycloak.token ?? '';
}

function authHeaders(): HeadersInit {
  const token = getToken();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const doFetch = () => fetch(url, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers as Record<string, string> || {}) },
  });

  let res = await doFetch();

  if (res.status === 401) {
    try {
      await keycloak.updateToken(30);
      res = await doFetch();
    } catch {
      keycloak.login({ redirectUri: window.location.origin + '/callback' });
      throw new Error('认证已过期，正在跳转登录...');
    }
  }

  return res;
}

export async function fetchWorkOrderList(): Promise<GeneratedWorkOrderSummary[]> {
  const res = await authFetch(BASE);
  if (!res.ok) throw new Error(`获取工单列表失败: ${res.status}`);
  return res.json();
}

export async function fetchWorkOrder(id: string): Promise<WorkOrderData> {
  const res = await authFetch(`${BASE}/${id}`);
  if (!res.ok) throw new Error(`获取工单失败: ${res.status}`);
  return res.json();
}

export async function submitReview(
  id: string, body: ReviewRequest
): Promise<ReviewResponse> {
  const res = await authFetch(`${BASE}/${id}/review`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
  if (res.status === 409) {
    throw new ConflictError((await res.json()).detail);
  }
  if (!res.ok) throw new Error(`提交审查失败: ${res.status}`);
  return res.json();
}

export class ConflictError extends Error {}

export async function acquireLock(id: string): Promise<LockStatus> {
  const res = await authFetch(`${BASE}/${id}/lock`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`获取锁失败: ${res.status}`);
  return res.json();
}

export async function releaseLock(id: string): Promise<void> {
  await authFetch(`${BASE}/${id}/lock`, {
    method: 'DELETE',
  });
}

export async function stashWorkOrder(
  id: string,
  fieldStates: Record<string, unknown>,
  notes: string,
  mode: 'manual' | 'auto_save' = 'manual',
): Promise<void> {
  const res = await authFetch(`${BASE}/${id}/stash`, {
    method: 'POST',
    body: JSON.stringify({ field_states: fieldStates, notes, mode }),
  });
  if (!res.ok) throw new Error(`暂存失败: ${res.status}`);
}

export interface StashData {
  field_states: Record<string, { currentValue: unknown; status: string; changeReason?: string }>;
  notes: string;
  updated_at: string | null;
}

export async function fetchStashData(id: string): Promise<StashData | null> {
  const res = await authFetch(`${BASE}/${id}/stash`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`获取暂存数据失败: ${res.status}`);
  return res.json();
}

export async function deleteStashData(id: string): Promise<void> {
  const res = await authFetch(`${BASE}/${id}/stash`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`删除暂存数据失败: ${res.status}`);
}

export async function heartbeatLock(id: string): Promise<'ok' | 'lost'> {
  const res = await authFetch(`${BASE}/${id}/lock`, {
    method: 'PUT',
  });
  if (res.status === 423) return 'lost';
  if (!res.ok) throw new Error(`心跳失败: ${res.status}`);
  return 'ok';
}

export interface ConfirmRequest {
  session_id: string;
  version: number;
  changes: { op: string; path: string; field_label: string; old_value?: unknown; new_value?: unknown }[];
  reject_reason: string | null;
  review_notes: string | null;
  idempotency_key: string;
}

export interface ConfirmResponse {
  review_id: string;
  workorder_id: string;
  status: 'confirmed' | 'rejected';
  change_count: number;
  bad_case_count: number;
  next_status: string;
  sync_status: 'pending' | 'synced' | 'failed';
}

export async function fetchConfirm(
  id: string, body: ConfirmRequest
): Promise<ConfirmResponse> {
  const res = await authFetch(`${BASE}/${id}/confirm`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
  if (res.status === 409) {
    throw new ConflictError((await res.json()).detail);
  }
  if (!res.ok) throw new Error(`确认提交失败: ${res.status}`);
  return res.json();
}

export async function fetchAuditLogs(id: string): Promise<GeneratedAuditLogEntry[]> {
  const res = await authFetch(`${BASE}/${id}/audit-logs`);
  if (!res.ok) throw new Error(`获取审计日志失败: ${res.status}`);
  return res.json();
}
