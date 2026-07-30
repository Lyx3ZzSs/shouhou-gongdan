import { ArrowRight } from 'lucide-react';
import { EMPTY_LABEL, formatValue } from '../../lib/format';
import type { FieldDef } from '../../types';
import { cn } from '@/lib/utils';

/** 字段修改差异：删除线原始值 → 高亮新值 */
export function FieldDiff({
  before,
  after,
  field,
  className,
}: {
  before: unknown;
  after: unknown;
  field?: FieldDef;
  className?: string;
}) {
  const b = formatValue(before, field);
  const a = formatValue(after, field);
  return (
    <span className={cn('inline-flex flex-wrap items-center gap-1.5 break-all text-sm', className)}>
      <span className="diff-del">{b === EMPTY_LABEL ? '空值' : b}</span>
      <ArrowRight className="h-3 w-3 shrink-0 text-primary/50" />
      <span className="diff-add">{a === EMPTY_LABEL ? '空值' : a}</span>
    </span>
  );
}
