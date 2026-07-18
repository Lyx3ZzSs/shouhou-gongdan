import { AlertCircle, Check, CloudOff, CloudUpload, Loader2, type LucideIcon } from 'lucide-react';
import type { AutoSaveStatus } from '../../types';
import { cn } from '@/lib/utils';

const META: Record<AutoSaveStatus, { label: string; icon: LucideIcon; cls: string; spin?: boolean }> = {
  idle: { label: '', icon: CloudUpload, cls: 'text-muted-foreground' },
  saving: { label: '保存中', icon: Loader2, cls: 'text-muted-foreground', spin: true },
  saved: { label: '已自动保存', icon: Check, cls: 'text-success' },
  failed: { label: '保存失败', icon: AlertCircle, cls: 'text-destructive' },
  offline: { label: '离线状态', icon: CloudOff, cls: 'text-destructive' },
};

export function AutoSaveIndicator({
  status,
  className,
}: {
  status: AutoSaveStatus;
  className?: string;
}) {
  if (status === 'idle') return null;
  const m = META[status];
  const Icon = m.icon;
  return (
    <span
      className={cn('inline-flex items-center gap-1 text-xs', m.cls, className)}
      role="status"
      aria-live="polite"
    >
      <Icon className={cn('h-3.5 w-3.5', m.spin && 'animate-spin')} />
      {m.label}
    </span>
  );
}
