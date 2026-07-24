import { Badge } from '@/components/ui/badge';
import { FieldGridItem } from './FieldGridItem';
import { useReviewStore } from '../../store/useReviewStore';
import type { FieldDef, FieldGroupId } from '../../types';
import { cn } from '@/lib/utils';

/**
 * FieldCard — 单个字段分组卡片。
 *
 * 每个卡片包含：
 * - 标题栏：分组名称 + 字段总数 + 异常计数 + 变更计数
 * - 内容区：响应式 Grid 排列 FieldGridItem（lg:3列 sm:2列 移动端:1列）
 */
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

  // 从实际渲染的 fields 计算计数，而非从 allGroupFields
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

  // 计算每个字段的列跨
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
    <div className="rounded-lg border border-border bg-card">
      {/* 标题栏 */}
      <div
        className={cn(
          'flex items-center gap-2 border-b border-border bg-muted/20 px-4',
          isCompact ? 'h-8' : 'h-10',
        )}
      >
        <span className="text-sm font-semibold text-foreground">
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

      {/* 字段网格：响应式列数 */}
      <div
        className={cn(
          'grid gap-px bg-border',
          'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
          isCompact ? 'text-xs' : 'text-sm',
        )}
      >
        {fields.map((f) => (
          <div key={f.id} className="bg-card">
            <FieldGridItem field={f} columnSpan={getColumnSpan(f)} />
          </div>
        ))}
      </div>
    </div>
  );
}
