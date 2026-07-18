import { cn } from '@/lib/utils';
import { useQueueStats } from '@/workbench/store/useReviewStore';

interface StatTile {
  label: string;
  value: number;
  destructive?: boolean;
}

export function QueueStatistics() {
  const { pending, nearTimeout, stashed, processed } = useQueueStats();

  const tiles: StatTile[] = [
    { label: '待审核', value: pending },
    { label: '即将超时', value: nearTimeout, destructive: nearTimeout > 0 },
    { label: '已暂存', value: stashed },
    { label: '今日已处理', value: processed },
  ];

  return (
    <div className="grid grid-cols-2 border-b border-border">
      {tiles.map((tile, idx) => (
        <div
          key={tile.label}
          className={cn(
            'px-3 py-2',
            idx % 2 === 0 && 'border-r border-border',
            idx < 2 && 'border-b border-border',
          )}
        >
          <div className="text-xs text-muted-foreground">{tile.label}</div>
          <div
            className={cn(
              'mt-0.5 text-lg font-semibold tabular-nums',
              tile.destructive && 'text-destructive',
            )}
          >
            {tile.value}
          </div>
        </div>
      ))}
    </div>
  );
}
