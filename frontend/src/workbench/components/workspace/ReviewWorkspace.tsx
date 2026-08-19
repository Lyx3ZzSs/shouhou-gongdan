import { Inbox, UserCog, X, Loader2, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { TicketReviewHeader } from './TicketReviewHeader';
import { KeyFieldReview } from './KeyFieldReview';
import { useReviewStore } from '../../store/useReviewStore';
import { useReviewLock } from '../../hooks/useReviewLock';

function BeingEditedBanner() {
  const beingEditedBy = useReviewStore((s) => s.beingEditedBy);
  const clearBeingEdited = useReviewStore((s) => s.clearBeingEdited);
  if (!beingEditedBy) return null;
  return (
    <div className="flex shrink-0 items-center gap-2 border-b border-warning/20 bg-warning/8 backdrop-blur-sm px-4 py-1.5 text-xs text-warning">
      <UserCog className="h-3.5 w-3.5 animate-pulse-soft" />
      <span>
        <span className="font-medium">{beingEditedBy}</span>{' '}
        正在编辑此工单，请留意并发冲突。
      </span>
      <Button
        variant="ghost"
        size="icon-sm"
        className="ml-auto h-5 w-5 text-warning rounded-lg hover:bg-warning/10"
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
    <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center text-muted-foreground">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted/30 border border-border/30">
        <Inbox className="h-8 w-8 opacity-40 animate-pulse-soft" />
      </div>
      <p className="text-sm font-medium">队列已清空</p>
      <p className="text-xs max-w-xs">
        今日审核已全部完成，或调整筛选条件查看更多工单。
      </p>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  const init = useReviewStore((s) => s.init);
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-destructive/8 border border-destructive/20">
        <AlertTriangle className="h-8 w-8 text-destructive/70" />
      </div>
      <p className="text-sm text-destructive max-w-md">{message}</p>
      <Button variant="outline" size="sm" onClick={() => init()} className="rounded-xl">
        重试
      </Button>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 text-muted-foreground">
      <div className="relative">
        <div className="h-10 w-10 rounded-full border-2 border-primary/20" />
        <Loader2 className="absolute inset-0 m-auto h-5 w-5 animate-spin text-primary" />
      </div>
      <span className="text-sm">加载工单详情...</span>
    </div>
  );
}

export function ReviewWorkspace() {
  const ticket = useReviewStore((s) => s.ticket);
  const ticketLoading = useReviewStore((s) => s.ticketLoading);
  const error = useReviewStore((s) => s.error);

  useReviewLock(ticket?.id);

  if (error) {
    return (
      <div className="flex min-w-0 flex-1 items-center justify-center bg-app">
        <ErrorState message={error} />
      </div>
    );
  }

  if (ticketLoading) {
    return (
      <div className="flex min-w-0 flex-1 items-center justify-center bg-app">
        <LoadingState />
      </div>
    );
  }

  if (!ticket) {
    return (
      <div className="flex min-w-0 flex-1 items-center justify-center bg-app">
        <EmptyState />
      </div>
    );
  }

  return (
    <main className="flex h-full min-h-0 min-w-0 flex-1 flex-col bg-app">
      <BeingEditedBanner />
      <TicketReviewHeader />
      <div className="flex-1 overflow-y-auto">
        <KeyFieldReview />
      </div>
    </main>
  );
}
