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
        className="flex-1 flex flex-col items-center justify-center gap-2 py-8 text-muted-foreground"
        role="status"
      >
        <Inbox className="h-8 w-8 opacity-50" />
        <span className="text-xs">没有符合筛选条件的工单</span>
      </div>
    );
  }

  return (
    <div
      className="flex-1 overflow-y-auto"
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
