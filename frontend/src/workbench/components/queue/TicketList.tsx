import { Inbox } from 'lucide-react';
import { useFilteredQueue, useReviewStore } from '@/workbench/store/useReviewStore';
import { TicketListItem } from './TicketListItem';

export function TicketList() {
  const items = useFilteredQueue();
  const selectedId = useReviewStore((s) => s.selectedId);
  const selectTicket = useReviewStore((s) => s.selectTicket);

  if (items.length === 0) {
    return (
      <div
        className="flex-1 flex flex-col items-center justify-center gap-3 py-8 text-muted-foreground px-4"
        role="status"
      >
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted/30 border border-border/30">
          <Inbox className="h-7 w-7 opacity-40" />
        </div>
        <span className="text-xs">没有符合筛选条件的工单</span>
      </div>
    );
  }

  return (
    <div
      className="flex-1 overflow-y-auto scroll-smooth px-1 py-1"
      role="list"
      aria-label="待审核工单列表"
    >
      {items.map((item) => (
        <TicketListItem
          key={item.id}
          item={item}
          selected={item.id === selectedId}
          onSelect={() => selectTicket(item.id)}
        />
      ))}
    </div>
  );
}
