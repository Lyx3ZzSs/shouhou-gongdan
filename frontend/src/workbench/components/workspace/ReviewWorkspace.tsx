import { Inbox, UserCog, X, Loader2, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { TicketReviewHeader } from './TicketReviewHeader';
import { ReviewToolbar } from './ReviewToolbar';
import { FieldReviewSections } from './FieldReviewSections';
import { useReviewStore } from '../../store/useReviewStore';
import { useReviewLock } from '../../hooks/useReviewLock';

function BeingEditedBanner() {
  const beingEditedBy = useReviewStore((s) => s.beingEditedBy);
  const clearBeingEdited = useReviewStore((s) => s.clearBeingEdited);
  if (!beingEditedBy) return null;
  return (
    <div className="flex shrink-0 items-center gap-2 border-b border-warning/30 bg-warning/10 px-4 py-1.5 text-xs text-warning">
      <UserCog className="h-3.5 w-3.5" />
      <span>
        <span className="font-medium">{beingEditedBy}</span> 正在编辑此工单，请留意并发冲突。
      </span>
      <Button
        variant="ghost"
        size="icon-sm"
        className="ml-auto h-5 w-5 text-warning"
        onClick={clearBeingEdited}
        aria-label="关闭提示"
      >
        <X className="h-3 w-3" />
      </Button>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center text-muted-foreground">
      <Inbox className="h-10 w-10 opacity-40" />
      <p className="text-sm font-medium">队列已清空</p>
      <p className="text-xs">今日审核已全部完成，或调整筛选条件查看更多工单。</p>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  const init = useReviewStore((s) => s.init);
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
      <AlertTriangle className="h-8 w-8 text-destructive opacity-60" />
      <p className="text-sm text-destructive max-w-md">{message}</p>
      <Button variant="outline" size="sm" onClick={() => init()}>
        重试
      </Button>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
      <Loader2 className="h-6 w-6 animate-spin" />
      <span className="text-sm">加载工单详情...</span>
    </div>
  );
}

export function ReviewWorkspace() {
  const ticket = useReviewStore((s) => s.ticket);
  const queueEmpty = useReviewStore((s) => s.queueEmpty);
  const ticketLoading = useReviewStore((s) => s.ticketLoading);
  const error = useReviewStore((s) => s.error);

  // 编辑锁：加载工单后获取，切换/卸载时释放
  useReviewLock(ticket?.id);

  if (error) {
    return (
      <div className="flex min-w-0 flex-1 items-center justify-center bg-background">
        <ErrorState message={error} />
      </div>
    );
  }

  if (ticketLoading) {
    return (
      <div className="flex min-w-0 flex-1 items-center justify-center bg-background">
        <LoadingState />
      </div>
    );
  }

  if (!ticket) {
    return (
      <div className="flex min-w-0 flex-1 items-center justify-center bg-background">
        <EmptyState />
      </div>
    );
  }

  return (
    <main className="flex min-w-0 flex-1 flex-col bg-background">
      <BeingEditedBanner />
      <TicketReviewHeader />
      <ReviewToolbar />
      <div className="flex-1 overflow-y-auto">
        <FieldReviewSections />
      </div>
      {queueEmpty && null}
    </main>
  );
}
