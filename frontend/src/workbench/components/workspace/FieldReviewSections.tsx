import { FilterX } from 'lucide-react';
import { FIELD_GROUPS } from '../../lib/constants';
import { useReviewStore } from '../../store/useReviewStore';
import { FieldGroup } from './FieldGroup';
import type { FieldDef } from '../../types';

export function FieldReviewSections() {
  const ticket = useReviewStore((s) => s.ticket);
  const fieldFilter = useReviewStore((s) => s.fieldFilter);
  const fieldStates = useReviewStore((s) => s.fieldStates);
  const anomalies = ticket?.anomalies ?? [];

  if (!ticket) return null;

  const anomalyFieldIds = new Set(anomalies.map((a) => a.fieldId).filter(Boolean));

  const isVisible = (f: FieldDef): boolean => {
    const st = fieldStates[f.id]?.status;
    if (fieldFilter === 'modified') return st === 'modified';
    if (fieldFilter === 'abnormal') {
      return (
        anomalyFieldIds.has(f.id) ||
        st === 'blocking_error' ||
        st === 'warning' ||
        st === 'low_confidence'
      );
    }
    return true;
  };

  const groups = FIELD_GROUPS.map((g) => ({
    group: g,
    fields: ticket.fields.filter((f) => f.group === g.id && isVisible(f)),
  })).filter((g) => g.fields.length > 0);

  if (groups.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center text-sm text-muted-foreground">
        <FilterX className="mb-2 h-8 w-8 opacity-50" />
        {fieldFilter === 'modified'
          ? '没有已修改的字段'
          : fieldFilter === 'abnormal'
            ? '没有异常字段'
            : '没有匹配的字段'}
      </div>
    );
  }

  return (
    <div className="divide-y divide-border">
      {groups.map(({ group, fields }) => (
        <FieldGroup key={group.id} group={group} fields={fields} />
      ))}
    </div>
  );
}
