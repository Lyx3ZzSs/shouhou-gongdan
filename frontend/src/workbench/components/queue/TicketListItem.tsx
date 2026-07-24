import type { KeyboardEvent } from 'react';
import { FileEdit, Lock, Save } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { SLACountdown } from '@/workbench/components/primitives/SLACountdown';
import { formatDateTime } from '@/workbench/lib/format';
import type { QueueItem, QueueItemStatus } from '@/workbench/types';

// 队列状态 -> 中文标签
const STATUS_LABEL: Record<QueueItemStatus, string> = {
  pending_review: '待审核',
  reviewing: '审核中',
  returned: '已退回',
  stashed: '已暂存',
};

// 队列状态 -> Badge 语义色
const STATUS_VARIANT: Record<
  QueueItemStatus,
  'muted' | 'default' | 'warning' | 'secondary'
> = {
  pending_review: 'muted',
  reviewing: 'default',
  returned: 'warning',
  stashed: 'secondary',
};

export interface TicketListItemProps {
  item: QueueItem;
  selected: boolean;
  onSelect: () => void;
}

export function TicketListItem({ item, selected, onSelect }: TicketListItemProps) {
  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onSelect();
    }
  };

  const showIndicators = Boolean(item.lockedByOther || item.stashed || item.modified);

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={handleKeyDown}
      title={`${item.serialNumber} ${item.title}`}
      aria-current={selected ? 'true' : undefined}
      className={cn(
        'relative min-h-[60px] px-3 py-2 border-b border-border cursor-pointer transition-colors outline-none',
        'hover:bg-accent/50 focus-visible:bg-accent/50 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring',
        selected && 'bg-primary/5',
      )}
    >
      {/* 选中态左侧高亮条 */}
      {selected && (
        <span className="absolute left-0 top-0 bottom-0 w-0.5 bg-primary" aria-hidden />
      )}

      {/* 行1：编号 + 状态 */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-muted-foreground">
          {item.serialNumber}
        </span>
        <Badge variant={STATUS_VARIANT[item.status]} className="ml-auto">
          {STATUS_LABEL[item.status]}
        </Badge>
      </div>

      {/* 行2：标题（单行截断） */}
      <div className="mt-1 text-sm truncate">{item.title}</div>

      {/* 行3：类型 · 异常 · SLA · 创建时间 */}
      <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
        <span className="truncate">{item.type}</span>
        {item.anomalyCount > 0 && (
          <Badge variant="warning" className="px-1 py-0">
            异常 {item.anomalyCount}
          </Badge>
        )}
        <SLACountdown remainingMin={item.slaRemainingMin} />
        <span className="ml-auto tabular-nums">{formatDateTime(item.createdAt)}</span>
      </div>

      {/* 行4：状态指示器（仅有相关标记时展示） */}
      {showIndicators && (
        <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
          {item.lockedByOther && (
            <span className="inline-flex items-center gap-1">
              <Lock className="h-3 w-3" />
              {item.lockedByOther} 编辑中
            </span>
          )}
          {item.stashed && (
            <span className="inline-flex items-center gap-1">
              <Save className="h-3 w-3" />
              已暂存
            </span>
          )}
          {item.modified && (
            <span className="inline-flex items-center gap-1 text-primary">
              <FileEdit className="h-3 w-3" />
              已修改
            </span>
          )}
        </div>
      )}
    </div>
  );
}
