import type {
  WorkOrderData, ReviewRequest, ReviewResponse,
  LockStatus,
} from '../pages/WorkOrderReview/types';
// Generated types from backend OpenAPI spec (openapi-typescript).
// Re-run `npm run generate-types` after backend schema changes to keep these in sync.
import type { components } from '../types/api';

// ---- Type aliases derived from the generated OpenAPI spec ----
// Prefer these over the manually-mirrored types in new code.
export type GeneratedWorkOrderSummary = components['schemas']['WorkOrderSummary'];
export type GeneratedWorkOrderResponse = components['schemas']['WorkOrderResponse'];
export type GeneratedReviewRequest = components['schemas']['ReviewRequest'];
export type GeneratedReviewResponse = components['schemas']['ReviewResponse'];
export type GeneratedLockStatus = components['schemas']['LockStatus'];
export type GeneratedAuditLogEntry = components['schemas']['AuditLogEntry'];

const BASE = '/api/workorders';

// WARNING: 硬编码 DEV_TOKEN 仅用于本地开发。
// 生产环境上线前必须替换为正式的 token 注入机制（如 OAuth2 登录流程、
// 环境变量 import.meta.env.VITE_API_TOKEN 或 AuthContext）。
// 此 token 会打包进浏览器 bundle，任何人可通过 DevTools 提取。
// Dev JWT token — generated against backend's dev JWT_SECRET.
const DEV_TOKEN =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZXYtdXNlciIsIm5hbWUiOiJEZXYgVXNlciIsInJvbGUiOiJjdXN0b21lcl9zZXJ2aWNlX2FnZW50IiwiZGVwYXJ0bWVudCI6IkRldiBEZXB0In0.XvTquXFV8KXXqBA5_AhnuiYvo8YeWGD_E3qglDnQsMA';

function authHeaders(): HeadersInit {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${DEV_TOKEN}`,
  };
}

export async function fetchWorkOrderList(): Promise<GeneratedWorkOrderSummary[]> {
  const res = await fetch(BASE, { headers: authHeaders() });
  if (!res.ok) throw new Error(`获取工单列表失败: ${res.status}`);
  return res.json();
}

export async function fetchWorkOrder(id: string): Promise<WorkOrderData> {
  const res = await fetch(`${BASE}/${id}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`获取工单失败: ${res.status}`);
  return res.json();
}

export async function submitReview(
  id: string, body: ReviewRequest
): Promise<ReviewResponse> {
  const res = await fetch(`${BASE}/${id}/review`, {
    method: 'POST',
    headers: authHeaders(),
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
  const res = await fetch(`${BASE}/${id}/lock`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`获取锁失败: ${res.status}`);
  return res.json();
}

export async function releaseLock(id: string): Promise<void> {
  await fetch(`${BASE}/${id}/lock`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
}

export async function stashWorkOrder(
  id: string,
  fieldStates: Record<string, unknown>,
  notes: string,
  mode: 'manual' | 'auto_save' = 'manual',
): Promise<void> {
  const res = await fetch(`${BASE}/${id}/stash`, {
    method: 'POST',
    headers: authHeaders(),
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
  const res = await fetch(`${BASE}/${id}/stash`, { headers: authHeaders() });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`获取暂存数据失败: ${res.status}`);
  return res.json();
}

export async function deleteStashData(id: string): Promise<void> {
  const res = await fetch(`${BASE}/${id}/stash`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`删除暂存数据失败: ${res.status}`);
}

export async function heartbeatLock(id: string): Promise<'ok' | 'lost'> {
  const res = await fetch(`${BASE}/${id}/lock`, {
    method: 'PUT',
    headers: authHeaders(),
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
  const res = await fetch(`${BASE}/${id}/confirm`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (res.status === 409) {
    throw new ConflictError((await res.json()).detail);
  }
  if (!res.ok) throw new Error(`确认提交失败: ${res.status}`);
  return res.json();
}

export async function fetchAuditLogs(id: string): Promise<GeneratedAuditLogEntry[]> {
  const res = await fetch(`${BASE}/${id}/audit-logs`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`获取审计日志失败: ${res.status}`);
  return res.json();
}
