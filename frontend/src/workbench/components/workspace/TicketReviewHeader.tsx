import { useEffect, useState } from 'react';
import { Check, Copy, LockKeyhole } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { SLACountdown } from '../primitives/SLACountdown';
import { useReviewStore } from '../../store/useReviewStore';

const STATUS_LABEL: Record<
  string,
  { label: string; variant: 'default' | 'warning' | 'success' | 'muted' }
> = {
  pending_review: { label: '待审核', variant: 'default' },
  reviewing: { label: '审核中', variant: 'warning' },
  returned: { label: '已退回', variant: 'warning' },
  rejected: { label: '已驳回', variant: 'muted' },
  approved: { label: '已通过', variant: 'success' },
  confirmed: { label: '已确认', variant: 'success' },
};

export function TicketReviewHeader() {
  const ticket = useReviewStore((s) => s.ticket);
  const beingEditedBy = useReviewStore((s) => s.beingEditedBy);
  const queue = useReviewStore((s) => s.queue);
  const selectedId = useReviewStore((s) => s.selectedId);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(false), 1500);
    return () => clearTimeout(t);
  }, [copied]);

  if (!ticket) return null;

  const statusInfo = STATUS_LABEL[ticket.status] ?? {
    label: ticket.status,
    variant: 'muted' as const,
  };
  const position = Math.max(0, queue.findIndex((item) => item.id === selectedId)) + 1;

  const copySerial = () => {
    navigator.clipboard?.writeText(ticket.serialNumber);
    setCopied(true);
  };

  return (
    <header className="shrink-0 border-b border-border bg-background">
      <div className="flex min-h-[72px] flex-wrap items-center gap-x-8 gap-y-2 border-b border-border px-5 py-3 lg:px-8">
        <div>
          <div className="text-xs text-muted-foreground">工单位置</div>
          <div className="mt-1 font-semibold tabular-nums">{position} / {queue.length}</div>
        </div>
        <div className="min-w-[220px]">
          <div className="text-xs text-muted-foreground">工单编号</div>
          <div className="mt-1 flex items-center gap-1.5 font-semibold">
            <span className="font-mono">{ticket.serialNumber}</span>
            <Button variant="ghost" size="icon-sm" className="h-5 w-5" onClick={copySerial} aria-label="复制工单编号">
              {copied ? <Check className="h-3 w-3 text-success" /> : <Copy className="h-3 w-3" />}
            </Button>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-8 text-sm">
          <div><span className="text-muted-foreground">SLA 剩余 </span><SLACountdown remainingMin={ticket.slaRemainingMin} /></div>
          <div className="text-success">自动暂存已开启</div>
          <div className="flex items-center gap-2 text-muted-foreground"><LockKeyhole className="h-4 w-4" />当前由你编辑</div>
        </div>
      </div>

      <div className="px-5 py-6 lg:px-8">
        <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="truncate text-2xl font-semibold leading-tight tracking-tight">
              {ticket.title}
            </h1>
            <Badge variant={statusInfo.variant}>{statusInfo.label}</Badge>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">核对关键字段，错误时直接修改；正确字段无需操作</p>
        </div>
      </div>
        {beingEditedBy && (
          <Badge variant="warning" className="mt-3 gap-1">
            并发编辑：{beingEditedBy} 正在编辑
          </Badge>
        )}
      </div>
    </header>
  );
}
