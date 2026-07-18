import { useMemo, useCallback } from 'react';
import { CheckCheck, ChevronRight } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { FieldReviewRow } from './FieldReviewRow';
import { useReviewStore } from '../../store/useReviewStore';
import type { FieldDef, FieldGroupId } from '../../types';
import { cn } from '@/lib/utils';

export function FieldGroup({
  group,
  fields,
}: {
  group: { id: FieldGroupId; name: string };
  fields: FieldDef[];
}) {
  const density = useReviewStore((s) => s.density);
  const expanded = useReviewStore((s) => s.expandedGroups[group.id] ?? false);
  const toggleGroup = useReviewStore((s) => s.toggleGroup);
  const fieldStates = useReviewStore((s) => s.fieldStates);
  const confirmField = useReviewStore((s) => s.confirmField);
  const ticket = useReviewStore((s) => s.ticket);

  const allGroupFields = useMemo(
    () => (ticket?.fields ?? []).filter((f) => f.group === group.id),
    [ticket, group.id],
  );
  const anomalies = ticket?.anomalies ?? [];

  const groupFieldIds = new Set(allGroupFields.map((f) => f.id));
  const anomalyCount = anomalies.filter(
    (a) => a.fieldId && groupFieldIds.has(a.fieldId),
  ).length;
  const modifiedCount = allGroupFields.filter(
    (f) => fieldStates[f.id]?.status === 'modified',
  ).length;

  // 本组中尚未确认的字段
  const unconfirmedCount = allGroupFields.filter(
    (f) => {
      const st = fieldStates[f.id];
      return st && st.status !== 'confirmed' && st.status !== 'modified';
    },
  ).length;

  const confirmAll = useCallback(() => {
    for (const f of allGroupFields) {
      const st = fieldStates[f.id];
      if (st && st.status !== 'confirmed' && st.status !== 'modified') {
        confirmField(f.id);
      }
    }
  }, [allGroupFields, fieldStates, confirmField]);

  return (
    <div>
      <div
        className={cn(
          'sticky top-0 z-10 flex items-center gap-2 border-b border-border bg-muted/40 backdrop-blur-sm',
          density === 'compact' ? 'h-8 px-3' : 'h-10 px-4',
        )}
      >
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => toggleGroup(group.id)}
          aria-label={expanded ? `收起 ${group.name}` : `展开 ${group.name}`}
          aria-expanded={expanded}
        >
          <ChevronRight className={cn('h-4 w-4 transition-transform', expanded && 'rotate-90')} />
        </Button>
        <span className="text-sm font-medium">{group.name}</span>
        <span className="text-xs text-muted-foreground">{allGroupFields.length} 字段</span>
        {anomalyCount > 0 && (
          <Badge variant="warning" className="text-[10px]">
            异常 {anomalyCount}
          </Badge>
        )}
        {modifiedCount > 0 && (
          <Badge variant="default" className="text-[10px]">
            已修改 {modifiedCount}
          </Badge>
        )}
        <div className="flex-1" />
        {unconfirmedCount > 0 && (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 gap-1 text-xs text-muted-foreground hover:text-success"
            onClick={confirmAll}
          >
            <CheckCheck className="h-3 w-3" />
            本组全部确认
          </Button>
        )}
        <button
          onClick={() => toggleGroup(group.id)}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          {expanded ? '收起' : '展开'}
        </button>
      </div>
      {expanded && (
        <div className="animate-fade-in">
          {fields.map((f, i) => (
            <FieldReviewRow key={f.id} field={f} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
