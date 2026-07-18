import { Badge } from '@/components/ui/badge';
import { STATUS_META } from '../../lib/constants';
import type { FieldReviewStatus } from '../../types';
import { cn } from '@/lib/utils';

export function StatusBadge({
  status,
  className,
}: {
  status: FieldReviewStatus;
  className?: string;
}) {
  const meta = STATUS_META[status];
  return (
    <Badge variant={meta.variant} className={cn('gap-1', className)}>
      {meta.label}
    </Badge>
  );
}
