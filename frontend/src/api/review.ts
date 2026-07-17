import type {
  WorkOrderData, ReviewRequest, ReviewResponse,
  LockStatus, AuditLogSession,
} from '../pages/WorkOrderReview/types';

const BASE = '/api/workorders';

export async function fetchWorkOrder(id: string): Promise<WorkOrderData> {
  const res = await fetch(`${BASE}/${id}`);
  if (!res.ok) throw new Error(`获取工单失败: ${res.status}`);
  return res.json();
}

export async function submitReview(
  id: string, body: ReviewRequest
): Promise<ReviewResponse> {
  const res = await fetch(`${BASE}/${id}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
  const res = await fetch(`${BASE}/${id}/lock`, { method: 'POST' });
  if (!res.ok) throw new Error(`获取锁失败: ${res.status}`);
  return res.json();
}

export async function releaseLock(id: string): Promise<void> {
  await fetch(`${BASE}/${id}/lock`, { method: 'DELETE' });
}

export async function heartbeatLock(id: string): Promise<'ok' | 'lost'> {
  const res = await fetch(`${BASE}/${id}/lock`, { method: 'PUT' });
  if (res.status === 423) return 'lost';
  if (!res.ok) throw new Error(`心跳失败: ${res.status}`);
  return 'ok';
}

export async function fetchAuditLogs(id: string): Promise<AuditLogSession[]> {
  const res = await fetch(`${BASE}/${id}/audit-logs`);
  if (!res.ok) throw new Error(`获取审计日志失败: ${res.status}`);
  return res.json();
}
