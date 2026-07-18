import { useState } from 'react';
import { Check, Copy, UserCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { RiskTag } from '../primitives/RiskTag';
import { SLACountdown } from '../primitives/SLACountdown';
import { ConfidenceBar } from '../primitives/ConfidenceBar';
import { useReviewStore } from '../../store/useReviewStore';
import { formatDateTime } from '../../lib/format';

const STATUS_LABEL: Record<string, { label: string; variant: 'default' | 'warning' | 'success' | 'muted' }> = {
  pending_review: { label: '待审核', variant: 'default' },
  reviewing: { label: '审核中', variant: 'warning' },
  returned: { label: '已退回', variant: 'warning' },
  rejected: { label: '已驳回', variant: 'muted' },
  approved: { label: '已通过', variant: 'success' },
};

export function TicketReviewHeader() {
  const ticket = useReviewStore((s) => s.ticket);
  const beingEditedBy = useReviewStore((s) => s.beingEditedBy);
  const [copied, setCopied] = useState(false);

  if (!ticket) return null;

  const statusInfo = STATUS_LABEL[ticket.status] ?? { label: ticket.status, variant: 'muted' as const };

  const copySerial = () => {
    navigator.clipboard?.writeText(ticket.serialNumber);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="shrink-0 border-b border-border bg-background px-5 py-3">
      {/* 第 1 行：标题 + 编号 + 主操作 */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="truncate text-lg font-semibold leading-tight">{ticket.title}</h1>
            <Badge variant={statusInfo.variant}>{statusInfo.label}</Badge>
            <RiskTag level={ticket.riskLevel} />
          </div>
          <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className="font-mono">{ticket.serialNumber}</span>
            <Button
              variant="ghost"
              size="icon-sm"
              className="h-5 w-5"
              onClick={copySerial}
              aria-label="复制工单编号"
            >
              {copied ? (
                <Check className="h-3 w-3 text-success" />
              ) : (
                <Copy className="h-3 w-3" />
              )}
            </Button>
            {copied && <span className="text-success">已复制</span>}
          </div>
        </div>

      </div>

      {/* 第 2 行：元信息 */}
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span>来源：{ticket.source}</span>
        <span>创建：{formatDateTime(ticket.createdAt)}</span>
        <span className="inline-flex items-center gap-1">
          SLA：<SLACountdown remainingMin={ticket.slaRemainingMin} />
        </span>
        <span className="inline-flex items-center gap-1.5">
          系统置信度：<ConfidenceBar value={ticket.systemConfidence} className="w-8" />
        </span>
        <span className="inline-flex items-center gap-1">
          <UserCircle2 className="h-3.5 w-3.5" />
          审核人：{ticket.reviewer}
        </span>
        {beingEditedBy && (
          <Badge variant="warning" className="gap-1">
            并发编辑：{beingEditedBy} 正在编辑
          </Badge>
        )}
      </div>
    </div>
  );
}
