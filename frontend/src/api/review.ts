import type {
  WorkOrderData, ReviewRequest, ReviewResponse,
  LockStatus,
} from '../types/review';
import type { components } from '../types/api';
import keycloak, { authEnabled } from '../auth/keycloak';

// ---- Type aliases derived from the generated OpenAPI spec ----
export type GeneratedWorkOrderSummary = components['schemas']['WorkOrderSummary'];
export type GeneratedWorkOrderResponse = components['schemas']['WorkOrderResponse'];
export type GeneratedReviewRequest = components['schemas']['ReviewRequest'];
export type GeneratedReviewResponse = components['schemas']['ReviewResponse'];
export type GeneratedLockStatus = components['schemas']['LockStatus'];
export type GeneratedAuditLogEntry = components['schemas']['AuditLogEntry'];
export type GeneratedPaginatedWorkOrderSummary = components['schemas']['PaginatedWorkOrderSummary'];

const BASE = '/api/workorders';

function getToken(): string {
  if (!authEnabled) return 'dev-token';
  return keycloak.token ?? '';
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

/** 从响应体中提取服务端返回的错误详情，失败时回退到状态码文本 */
async function extractErrorDetail(res: Response, fallbackStatus: string): Promise<string> {
  try {
    const body = await res.json();
    if (body?.detail && typeof body.detail === 'string') {
      return `${fallbackStatus}: ${body.detail}`;
    }
  } catch {
    // 响应体非 JSON，回退到状态码
  }
  return fallbackStatus;
}

/** 合并 HeadersInit 为普通 Record，避免 as 断言导致运行时错误 */
function mergeHeaders(initHeaders: RequestInit['headers']): Record<string, string> {
  const merged: Record<string, string> = { ...authHeaders() };
  if (!initHeaders) return merged;

  if (initHeaders instanceof Headers) {
    initHeaders.forEach((value, key) => { merged[key] = value; });
  } else if (Array.isArray(initHeaders)) {
    for (const [key, value] of initHeaders) {
      merged[key] = value;
    }
  } else {
    Object.assign(merged, initHeaders);
  }
  return merged;
}

export async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const doFetch = () => {
    const headers = mergeHeaders(options.headers);
    return fetch(url, {
      ...options,
      headers,
    });
  };

  let res: Response;
  try {
    res = await doFetch();
  } catch (err) {
    throw new Error(`网络请求失败: ${url} — ${(err as Error).message}`);
  }

  if (res.status === 401 && authEnabled) {
    try {
      await keycloak.updateToken(30);
      try {
        res = await doFetch();
      } catch (err) {
        throw new Error(`Token 刷新后请求失败: ${url} — ${(err as Error).message}`);
      }
    } catch {
      keycloak.login({ redirectUri: window.location.origin + '/callback' });
      throw new Error('认证已过期，正在跳转登录...');
    }
  }

  return res;
}

export async function fetchWorkOrderList(status?: string, keyword?: string): Promise<GeneratedWorkOrderSummary[]> {
  return (await fetchWorkOrderPage(status, keyword)).items;
}

export async function fetchNextWorkOrder(): Promise<string | null> {
  const res = await authFetch(`${BASE}/next`, { method: 'POST' });
  if (!res.ok) throw new Error(await extractErrorDetail(res, `领取下一张工单失败: ${res.status}`));
  return ((await res.json()) as { workorder_id: string | null }).workorder_id;
}

export interface StationOption {
  case_account_id: string;
  station_name: string | null;
  project_name: string | null;
}

export interface EmployeeOption {
  job_number: string;
  name: string | null;
  dept_name: string | null;
}

export interface ReviewContext {
  conversation: { role: string; content: string }[];
  attachments: { file_name: string | null; file_path: string | null }[];
  ledger: Record<string, string | null> | null;
}

async function fetchLookup<T>(kind: 'stations' | 'employees', keyword: string): Promise<T[]> {
  const res = await authFetch(`${BASE}/lookups/${kind}?keyword=${encodeURIComponent(keyword)}`);
  if (!res.ok) throw new Error(await extractErrorDetail(res, `获取候选项失败: ${res.status}`));
  return res.json();
}

export const fetchStationOptions = (keyword: string) => fetchLookup<StationOption>('stations', keyword);
export const fetchEmployeeOptions = (keyword: string) => fetchLookup<EmployeeOption>('employees', keyword);

export async function fetchReviewContext(id: string): Promise<ReviewContext> {
  const res = await authFetch(`${BASE}/${id}/context`);
  if (!res.ok) throw new Error(await extractErrorDetail(res, `获取核对材料失败: ${res.status}`));
  return res.json();
}

export async function fetchWorkOrderPage(
  status?: string,
  keyword?: string,
  offset = 0,
  limit = 50,
  createdFrom?: string,
  createdTo?: string,
): Promise<GeneratedPaginatedWorkOrderSummary> {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (keyword) params.set('keyword', keyword);
  params.set('offset', String(offset));
  params.set('limit', String(limit));
  if (createdFrom) params.set('created_from', createdFrom);
  if (createdTo) params.set('created_to', createdTo);
  const query = params.size ? `?${params}` : '';
  const res = await authFetch(`${BASE}${query}`);
  if (!res.ok) throw new Error(await extractErrorDetail(res, `获取工单列表失败: ${res.status}`));
  return res.json();
}

export async function fetchWorkOrder(id: string): Promise<WorkOrderData> {
  const res = await authFetch(`${BASE}/${id}`);
  if (!res.ok) throw new Error(await extractErrorDetail(res, `获取工单失败: ${res.status}`));
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
  if (!res.ok) throw new Error(await extractErrorDetail(res, `提交审查失败: ${res.status}`));
  return res.json();
}

export class ConflictError extends Error {
  /** 服务端当前版本号（409 时返回），null 表示后端未携带 */
  version: number | null;
  /** 服务端当前工单状态（409 时返回） */
  reviewStatus: string | null;

  constructor(detail: unknown) {
    const info = (typeof detail === 'object' && detail !== null ? detail : {}) as {
      message?: string;
      version?: number | null;
      review_status?: string | null;
    };
    super(typeof detail === 'string' ? detail : (info.message ?? '版本冲突，请刷新重试'));
    this.version = typeof detail === 'string' ? null : (info.version ?? null);
    this.reviewStatus = typeof detail === 'string' ? null : (info.review_status ?? null);
  }
}
export class LockLostError extends Error {}
export class ValidationError extends Error {
  issues: Array<{ code: string; severity: 'blocking' | 'warning' | 'info'; field: string | null; message: string }>;

  constructor(detail: unknown) {
    const info = (typeof detail === 'object' && detail !== null ? detail : {}) as {
      message?: string;
      issues?: ValidationError['issues'];
    };
    super(info.message ?? '工单存在阻断问题，无法确认');
    this.issues = info.issues ?? [];
  }
}

export async function acquireLock(id: string): Promise<LockStatus> {
  const res = await authFetch(`${BASE}/${id}/lock`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(await extractErrorDetail(res, `获取锁失败: ${res.status}`));
  return res.json();
}

export async function releaseLock(id: string, fencingToken: number): Promise<void> {
  await authFetch(`${BASE}/${id}/lock`, {
    method: 'DELETE',
    headers: { 'X-Lock-Fencing-Token': String(fencingToken) },
  });
}

export async function stashWorkOrder(
  id: string,
  fieldStates: Record<string, unknown>,
  notes: string,
  mode: 'manual' | 'auto_save' = 'manual',
  fencingToken: number,
): Promise<void> {
  const res = await authFetch(`${BASE}/${id}/stash`, {
    method: 'POST',
    body: JSON.stringify({ field_states: fieldStates, notes, mode, lock_fencing_token: fencingToken }),
  });
  if (res.status === 409) throw new ConflictError((await res.json()).detail);
  if (res.status === 423) throw new LockLostError(await extractErrorDetail(res, '编辑锁已失效'));
  if (!res.ok) throw new Error(await extractErrorDetail(res, `暂存失败: ${res.status}`));
}

export interface StashData {
  field_states: Record<string, { currentValue: unknown; status: string; changeReason?: string }>;
  notes: string;
  updated_at: string | null;
}

export async function fetchStashData(id: string): Promise<StashData | null> {
  const res = await authFetch(`${BASE}/${id}/stash`);
  // 兼容滚动发布期间仍以 404 表示“无暂存”的旧后端。
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(await extractErrorDetail(res, `获取暂存数据失败: ${res.status}`));
  return res.json();
}

export async function deleteStashData(id: string, fencingToken: number): Promise<void> {
  const res = await authFetch(`${BASE}/${id}/stash`, {
    method: 'DELETE',
    headers: { 'X-Lock-Fencing-Token': String(fencingToken) },
  });
  if (!res.ok) throw new Error(await extractErrorDetail(res, `删除暂存数据失败: ${res.status}`));
}

export async function heartbeatLock(id: string, fencingToken: number): Promise<'ok' | 'lost'> {
  const res = await authFetch(`${BASE}/${id}/lock`, {
    method: 'PUT',
    headers: { 'X-Lock-Fencing-Token': String(fencingToken) },
  });
  if (res.status === 423) return 'lost';
  if (!res.ok) throw new Error(await extractErrorDetail(res, `心跳失败: ${res.status}`));
  return 'ok';
}

export interface ConfirmRequest {
  session_id: string;
  version: number;
  changes: { op: string; path: string; field_label: string; old_value?: unknown; new_value?: unknown }[];
  reject_reason: string | null;
  review_notes: string | null;
  idempotency_key: string;
  lock_fencing_token: number;
}

export interface ConfirmResponse {
  review_id: string;
  workorder_id: string;
  status: 'confirmed' | 'rejected';
  change_count: number;
  bad_case_count: number;
  next_review_status: string;
  sync_status: 'pending' | 'syncing' | 'synced' | 'failed' | 'uncertain';
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
  // 423 Locked：编辑锁未持有/已失效，交由 UI 提示重新获取锁
  if (res.status === 423) {
    throw new LockLostError(await extractErrorDetail(res, '编辑锁已失效'));
  }
  if (res.status === 422) {
    const body = await res.json();
    throw new ValidationError(body.detail);
  }
  if (!res.ok) throw new Error(await extractErrorDetail(res, `确认提交失败: ${res.status}`));
  return res.json();
}

export async function fetchAuditLogs(id: string): Promise<GeneratedAuditLogEntry[]> {
  const res = await authFetch(`${BASE}/${id}/audit-logs`);
  if (!res.ok) throw new Error(await extractErrorDetail(res, `获取审计日志失败: ${res.status}`));
  return res.json();
}

export async function reconcileSync(id: string, externalId: string): Promise<void> {
  const res = await authFetch(`/api/admin/sync-uncertain/${id}/reconcile`, {
    method: 'POST',
    body: JSON.stringify({ external_id: externalId }),
  });
  if (!res.ok) throw new Error(await extractErrorDetail(res, `人工对账失败: ${res.status}`));
}

export async function confirmSyncNotCreated(id: string): Promise<void> {
  const res = await authFetch(`/api/admin/sync-uncertain/${id}/confirm-not-created`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(await extractErrorDetail(res, `核实未创建失败: ${res.status}`));
}

export async function retrySync(id: string): Promise<void> {
  const res = await authFetch(`/api/admin/sync-failures/${id}/retry`, { method: 'POST' });
  if (!res.ok) throw new Error(await extractErrorDetail(res, `同步重试失败: ${res.status}`));
}

export interface SyncFailure {
  id: string;
  ticket_id: number;
  sync_attempts: number;
  sync_last_error: string | null;
  sync_status: 'failed' | 'uncertain';
  sync_external_id: string | null;
  reviewed_at: string | null;
}

export async function fetchSyncFailures(): Promise<SyncFailure[]> {
  const res = await authFetch('/api/admin/sync-failures');
  if (!res.ok) throw new Error(await extractErrorDetail(res, `获取同步失败列表失败: ${res.status}`));
  return res.json();
}
