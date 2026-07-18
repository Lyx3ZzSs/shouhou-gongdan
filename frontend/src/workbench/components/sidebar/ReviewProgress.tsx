import { ListChecks } from 'lucide-react';
import { useReviewProgress, useReviewStore } from '../../store/useReviewStore';
import type { FieldFilter } from '../../types';
import { cn } from '@/lib/utils';

interface StatCell {
  key: string;
  label: string;
  value: number;
  valueClass: string;
  filter: FieldFilter;
}

export function ReviewProgress() {
  const { total, confirmed, modified, pendingAnomalies, unconfirmedKeyFields } =
    useReviewProgress();
  const setFieldFilter = useReviewStore((s) => s.setFieldFilter);

  const done = confirmed + modified;
  const pct = total > 0 ? Math.min(100, (done / total) * 100) : 0;

  const cells: StatCell[] = [
    {
      key: 'confirmed',
      label: '已确认',
      value: confirmed,
      valueClass: 'text-success',
      filter: 'all',
    },
    {
      key: 'modified',
      label: '已修改',
      value: modified,
      valueClass: 'text-primary',
      filter: 'modified',
    },
    {
      key: 'anomalies',
      label: '待处理异常',
      value: pendingAnomalies,
      valueClass: pendingAnomalies > 0 ? 'text-warning' : 'text-muted-foreground',
      filter: 'abnormal',
    },
    {
      key: 'keyFields',
      label: '未确认关键字段',
      value: unconfirmedKeyFields,
      valueClass: unconfirmedKeyFields > 0 ? 'text-destructive' : 'text-muted-foreground',
      filter: 'abnormal',
    },
  ];

  return (
    <section className="flex flex-col">
      <div className="flex items-center gap-2 px-3 pb-2 pt-3">
        <ListChecks className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">审核完成度</span>
      </div>

      <div className="px-3 pb-3">
        <div className="flex items-baseline gap-1.5">
          <span className="text-2xl font-semibold tabular-nums text-foreground">{done}</span>
          <span className="text-sm tabular-nums text-muted-foreground">/ {total}</span>
        </div>
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 border-t border-border">
        {cells.map((cell, idx) => (
          <button
            key={cell.key}
            type="button"
            onClick={() => setFieldFilter(cell.filter)}
            aria-label={`${cell.label}：${cell.value}，点击按此筛选字段`}
            className={cn(
              'flex flex-col items-start gap-0.5 px-3 py-2 text-left transition-colors hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-ring',
              idx % 2 === 0 && 'border-r border-border',
              idx < 2 && 'border-b border-border',
            )}
          >
            <span className="text-xs text-muted-foreground">{cell.label}</span>
            <span className={cn('text-base font-semibold tabular-nums', cell.valueClass)}>
              {cell.value}
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
