import isEqual from 'lodash.isequal';
import type { FieldDef } from '../types';

export const EMPTY_LABEL = '空';

export function isEmpty(v: unknown): boolean {
  if (v == null) return true;
  if (typeof v === 'string') return v.trim() === '';
  if (Array.isArray(v)) return v.length === 0;
  return false;
}

export function formatValue(v: unknown, field?: FieldDef): string {
  if (isEmpty(v)) return EMPTY_LABEL;
  if (field?.type === 'select' && field.options) {
    const opt = field.options.find((o) => String(o.value) === String(v));
    if (opt) return opt.label;
  }
  if (field?.type === 'datetime' && typeof v === 'string') {
    return formatDateTime(v);
  }
  if (field?.type === 'tags' && Array.isArray(v)) {
    return (v as string[]).join('、');
  }
  if (typeof v === 'boolean') return v ? '是' : '否';
  if (typeof v === 'number') return field?.unit ? `${v} ${field.unit}` : String(v);
  return String(v);
}

export function valuesEqual(a: unknown, b: unknown): boolean {
  return isEqual(a, b);
}

function pad(n: number) {
  return String(n).padStart(2, '0');
}

export function formatTime(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
    d.getHours(),
  )}:${pad(d.getMinutes())}`;
}

export function slaStatus(
  remainingMin: number,
): { label: string; tone: 'normal' | 'warning' | 'danger' } {
  if (remainingMin < 0) return { label: `已超时 ${Math.abs(remainingMin)} 分钟`, tone: 'danger' };
  if (remainingMin <= 30) return { label: `剩余 ${remainingMin} 分钟`, tone: 'danger' };
  if (remainingMin <= 60) return { label: `剩余 ${remainingMin} 分钟`, tone: 'warning' };
  return { label: `剩余 ${remainingMin} 分钟`, tone: 'normal' };
}

export function nowIso(): string {
  return new Date().toISOString();
}
