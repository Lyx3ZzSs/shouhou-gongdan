import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Check, Copy, UserCircle2 } from 'lucide-react';
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

  const copySerial = () => {
    navigator.clipboard?.writeText(ticket.serialNumber);
    setCopied(true);
  };

  return (
    <div className="shrink-0 border-b border-border/30 bg-transparent px-5 py-3.5">
      {/* 第 1 行：标题 + 状态 */}
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="truncate text-lg font-semibold leading-tight tracking-tight">
              {ticket.title}
            </h1>
            <Badge variant={statusInfo.variant}>{statusInfo.label}</Badge>
          </div>
          <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className="font-mono bg-muted/40 rounded-md px-1.5 py-0.5">{ticket.serialNumber}</span>
            <motion.div whileTap={{ scale: 0.85 }}>
              <Button
                variant="ghost"
                size="icon-sm"
                className="h-5 w-5 rounded-lg"
                onClick={copySerial}
                aria-label="复制工单编号"
              >
                {copied ? (
                  <Check className="h-3 w-3 text-success" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
              </Button>
            </motion.div>
            {copied && (
              <motion.span
                initial={{ opacity: 0, x: -4 }}
                animate={{ opacity: 1, x: 0 }}
                className="text-success"
              >
                已复制
              </motion.span>
            )}
          </div>
        </div>
      </div>

      {/* 第 2 行：元信息 */}
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1 bg-muted/30 backdrop-blur-sm rounded-full px-2.5 py-0.5">
          来源：{ticket.source}
        </span>
        <span className="inline-flex items-center gap-1 bg-muted/30 backdrop-blur-sm rounded-full px-2.5 py-0.5">
          创建：
          {new Date(ticket.createdAt).toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
          })}
        </span>
        <span className="inline-flex items-center gap-1 bg-muted/30 backdrop-blur-sm rounded-full px-2.5 py-0.5">
          SLA：
          <SLACountdown remainingMin={ticket.slaRemainingMin} />
        </span>
        <span className="inline-flex items-center gap-1 bg-muted/30 backdrop-blur-sm rounded-full px-2.5 py-0.5">
          <UserCircle2 className="h-3.5 w-3.5" />
          审核人：{ticket.reviewer}
        </span>
        {beingEditedBy && (
          <Badge variant="warning" className="gap-1 animate-pulse-soft">
            并发编辑：{beingEditedBy} 正在编辑
          </Badge>
        )}
      </div>
    </div>
  );
}
