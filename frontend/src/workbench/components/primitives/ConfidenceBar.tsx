import { cn } from '@/lib/utils';
import { LOW_CONFIDENCE_THRESHOLD } from '../../lib/constants';

export function ConfidenceBar({
  value,
  className,
  showLabel = true,
}: {
  value: number | null | undefined;
  className?: string;
  showLabel?: boolean;
}) {
  if (value == null) {
    return <span className={cn('text-xs text-muted-foreground', className)}>—</span>;
  }
  const low = value < LOW_CONFIDENCE_THRESHOLD;
  return (
    <div className={cn('flex items-center gap-1.5', className)} title={`系统置信度 ${value}%`}>
      <div className="h-1.5 w-10 overflow-hidden rounded-full bg-muted">
        <div
          className={cn('h-full rounded-full', low ? 'bg-warning' : 'bg-success')}
          style={{ width: `${Math.max(4, value)}%` }}
        />
      </div>
      {showLabel && (
        <span
          className={cn(
            'text-xs tabular-nums',
            low ? 'font-medium text-warning' : 'text-muted-foreground',
          )}
        >
          {value}%
        </span>
      )}
    </div>
  );
}
