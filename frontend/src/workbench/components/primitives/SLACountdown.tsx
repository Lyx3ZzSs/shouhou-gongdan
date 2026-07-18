import { Clock } from 'lucide-react';
import { slaStatus } from '../../lib/format';
import { cn } from '@/lib/utils';

export function SLACountdown({
  remainingMin,
  className,
}: {
  remainingMin: number;
  className?: string;
}) {
  const s = slaStatus(remainingMin);
  const tone =
    s.tone === 'danger'
      ? 'text-destructive'
      : s.tone === 'warning'
        ? 'text-warning'
        : 'text-muted-foreground';
  return (
    <span
      className={cn('inline-flex items-center gap-1 text-xs font-medium tabular-nums', tone, className)}
      title="SLA 剩余时间"
    >
      <Clock className="h-3.5 w-3.5" />
      {s.label}
    </span>
  );
}
