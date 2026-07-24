import { ArrowDown, Maximize2, Minimize2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useReviewStore, useReviewProgress, useEffectiveChanges } from '../../store/useReviewStore';
import type { FieldFilter } from '../../types';
import { cn } from '@/lib/utils';

const FILTERS: { value: FieldFilter; label: string }[] = [
  { value: 'all', label: '查看全部字段' },
  { value: 'abnormal', label: '只看异常字段' },
  { value: 'modified', label: '只看已修改字段' },
];

export function ReviewToolbar() {
  const fieldFilter = useReviewStore((s) => s.fieldFilter);
  const setFieldFilter = useReviewStore((s) => s.setFieldFilter);
  const density = useReviewStore((s) => s.density);
  const toggleDensity = useReviewStore((s) => s.toggleDensity);
  const jumpToNextAnomaly = useReviewStore((s) => s.jumpToNextAnomaly);
  const progress = useReviewProgress();
  const changes = useEffectiveChanges();

  return (
    <div className="sticky top-0 z-20 flex h-10 shrink-0 items-center gap-1 border-b border-border bg-background px-4">
      <div className="flex items-center gap-0.5 rounded-md border border-border p-0.5">
        {FILTERS.map((f) => {
          const anomalyCount = progress.pendingAnomalies;
          const modifiedCount = changes.length;
          return (
            <button
              key={f.value}
              onClick={() => setFieldFilter(f.value)}
              aria-pressed={fieldFilter === f.value}
              className={cn(
                'rounded-[5px] px-2.5 py-1 text-xs font-medium transition-colors',
                fieldFilter === f.value
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-foreground',
              )}
            >
              {f.label}
              {f.value === 'abnormal' && anomalyCount > 0 && (
                <span
                  className={cn(
                    'ml-1 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full px-1 text-[10px] tabular-nums',
                    fieldFilter === f.value
                      ? 'bg-primary-foreground/20 text-primary-foreground'
                      : 'bg-warning/20 text-warning',
                  )}
                >
                  {anomalyCount}
                </span>
              )}
              {f.value === 'modified' && modifiedCount > 0 && (
                <span
                  className={cn(
                    'ml-1 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full px-1 text-[10px] tabular-nums',
                    fieldFilter === f.value
                      ? 'bg-primary-foreground/20 text-primary-foreground'
                      : 'bg-primary/20 text-primary',
                  )}
                >
                  {modifiedCount}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div className="flex-1" />
      <TooltipProvider delayDuration={300}>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={toggleDensity}
              aria-label={density === 'standard' ? '切换为紧凑模式' : '切换为标准模式'}
            >
              {density === 'standard' ? (
                <Minimize2 className="h-3.5 w-3.5" />
              ) : (
                <Maximize2 className="h-3.5 w-3.5" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent>{density === 'standard' ? '紧凑模式' : '标准模式'}</TooltipContent>
        </Tooltip>
      </TooltipProvider>
      <Button variant="ghost" size="sm" onClick={jumpToNextAnomaly} className="gap-1.5 text-xs">
        <ArrowDown className="h-3.5 w-3.5" />
        跳到下一个问题
        <kbd className="ml-1 rounded border border-border bg-muted px-1 text-[10px] text-muted-foreground">
          Alt+↓
        </kbd>
      </Button>
    </div>
  );
}
