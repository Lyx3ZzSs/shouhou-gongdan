import { motion } from 'framer-motion';
import { Badge } from '@/components/ui/badge';
import { FieldGridItem } from './FieldGridItem';
import { useReviewStore } from '../../store/useReviewStore';
import type { FieldDef, FieldGroupId } from '../../types';
import { cn } from '@/lib/utils';
import { staggerContainer, staggerItem } from '@/lib/animations';

export function FieldCard({
  group,
  fields,
}: {
  group: { id: FieldGroupId; name: string };
  fields: FieldDef[];
}) {
  const density = useReviewStore((s) => s.density);
  const fieldStates = useReviewStore((s) => s.fieldStates);
  const anomalies = useReviewStore((s) => s.ticket?.anomalies) ?? [];
  const isCompact = density === 'compact';

  const fieldIds = new Set(fields.map((f) => f.id));
  const anomalyCount = anomalies.filter(
    (a) => a.fieldId && fieldIds.has(a.fieldId),
  ).length;
  const modifiedCount = fields.filter(
    (f) => fieldStates[f.id]?.status === 'modified',
  ).length;
  const blockingCount = anomalies.filter(
    (a) =>
      a.type === 'blocking_error' &&
      a.fieldId &&
      fieldIds.has(a.fieldId),
  ).length;

  function getColumnSpan(f: FieldDef): 1 | 2 | 3 {
    if (f.type === 'textarea') return 3;
    const val = fieldStates[f.id]?.currentValue ?? f.originalValue;
    const strVal = typeof val === 'string' ? val : String(val ?? '');
    if (strVal.length > 80) return 2;
    if (f.type === 'select' && f.options && f.options.length > 5) return 2;
    return 1;
  }

  if (fields.length === 0) return null;

  return (
    <motion.div
      className="rounded-2xl border border-border/40 bg-card/80 backdrop-blur-sm shadow-glass-sm hover:shadow-glass-md transition-shadow duration-300"
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
    >
      {/* 标题栏 */}
      <div
        className={cn(
          'flex items-center gap-2 border-b border-border/20 bg-muted/20 rounded-t-2xl px-4',
          isCompact ? 'h-8' : 'h-10',
        )}
      >
        <span className="text-sm font-semibold tracking-tight text-foreground">
          {group.name}
        </span>
        <span className="text-xs text-muted-foreground">
          {fields.length} 字段
        </span>
        {blockingCount > 0 && (
          <Badge variant="destructive" className="text-[10px]">
            阻断 {blockingCount}
          </Badge>
        )}
        {anomalyCount > 0 && blockingCount === 0 && (
          <Badge variant="warning" className="text-[10px]">
            异常 {anomalyCount}
          </Badge>
        )}
        {modifiedCount > 0 && (
          <Badge variant="default" className="text-[10px]">
            已修改 {modifiedCount}
          </Badge>
        )}
      </div>

      {/* 字段网格 */}
      <div
        className={cn(
          'grid gap-px bg-border/30',
          'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
          isCompact ? 'text-xs' : 'text-sm',
        )}
      >
        {fields.map((f) => (
          <motion.div key={f.id} className="bg-card/60" variants={staggerItem}>
            <FieldGridItem field={f} columnSpan={getColumnSpan(f)} />
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
