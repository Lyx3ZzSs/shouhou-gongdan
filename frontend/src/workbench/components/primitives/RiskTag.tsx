import { Badge } from '@/components/ui/badge';
import { RISK_META } from '../../lib/constants';
import type { RiskLevel } from '../../types';
import { cn } from '@/lib/utils';

export function RiskTag({ level, className }: { level: RiskLevel; className?: string }) {
  const meta = RISK_META[level];
  return (
    <Badge variant={meta.variant} className={cn('gap-1', className)}>
      <span className={cn('h-1.5 w-1.5 rounded-full', meta.dot)} />
      {meta.label}
    </Badge>
  );
}
