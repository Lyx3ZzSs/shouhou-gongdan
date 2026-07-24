import { FilterX } from 'lucide-react';
import { FIELD_GROUPS } from '../../lib/constants';
import { useReviewStore } from '../../store/useReviewStore';
import { FieldCard } from './FieldCard';
import type { FieldDef } from '../../types';

/**
 * FieldCards — 分组卡片容器，替换旧的 FieldReviewSections。
 *
 * 根据 fieldFilter 筛选可见分组，
 * 然后将每个分组的字段以卡片形式渲染。
 * 所有分组默认全部展开。
 */
export function FieldCards() {
  const ticket = useReviewStore((s) => s.ticket);
  const fieldFilter = useReviewStore((s) => s.fieldFilter);
  const fieldStates = useReviewStore((s) => s.fieldStates);
  const anomalies = ticket?.anomalies ?? [];

  if (!ticket) return null;

  const anomalyFieldIds = new Set(
    anomalies.map((a) => a.fieldId).filter(Boolean),
  );

  // 字段可见性筛选
  const isVisible = (f: FieldDef): boolean => {
    const st = fieldStates[f.id]?.status;
    if (fieldFilter === 'modified') return st === 'modified';
    if (fieldFilter === 'abnormal') {
      return (
        anomalyFieldIds.has(f.id) ||
        st === 'blocking_error' ||
        st === 'warning'
      );
    }
    return true;
  };

  // 按分组聚合可见字段
  const visibleGroups = FIELD_GROUPS.map((g) => ({
    group: g,
    fields: ticket.fields.filter((f) => f.group === g.id && isVisible(f)),
  })).filter((g) => g.fields.length > 0);

  // 空状态
  if (visibleGroups.length === 0) {
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
    <div className="flex flex-col gap-4 px-4 py-4">
      {visibleGroups.map(({ group, fields }) => (
        <FieldCard key={group.id} group={group} fields={fields} />
      ))}
    </div>
  );
}
