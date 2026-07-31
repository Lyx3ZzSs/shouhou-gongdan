import { PanelLeftClose, Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useFilteredQueue, useReviewStore } from '@/workbench/store/useReviewStore';
import { TicketList } from './TicketList';

export function ReviewQueue() {
  const items = useFilteredQueue();
  const toggleLeft = useReviewStore((s) => s.toggleLeft);
  const queueLoading = useReviewStore((s) => s.queueLoading);
  const queue = useReviewStore((s) => s.queue);

  return (
    <div className="w-72 shrink-0 border-r border-border/40 bg-background/80 backdrop-blur-xl flex flex-col">
      {/* 顶栏：标题 + 计数 + 收起按钮 */}
      <div className="flex h-12 items-center gap-2 px-3 border-b border-border/30">
        <h2 className="text-sm font-semibold tracking-tight">待审核队列</h2>
        {queueLoading ? (
          <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
        ) : (
          <Badge variant="muted" className="tabular-nums">
            {items.length}
          </Badge>
        )}
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={toggleLeft}
          aria-label="收起队列"
          className="ml-auto rounded-xl hover:bg-accent/50"
        >
          <PanelLeftClose className="h-4 w-4" />
        </Button>
      </div>

      {queueLoading && queue.length === 0 ? (
        <div className="flex-1 space-y-1 p-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div
              key={i}
              className="h-[60px] rounded-lg border border-border/30 bg-gradient-to-r from-transparent via-muted/20 to-transparent bg-[length:200%_100%] animate-shimmer px-3 py-2"
            >
              <div className="h-3 w-2/3 rounded bg-muted/50 mb-2" />
              <div className="h-3 w-1/2 rounded bg-muted/40" />
            </div>
          ))}
        </div>
      ) : (
        <TicketList />
      )}
    </div>
  );
}
