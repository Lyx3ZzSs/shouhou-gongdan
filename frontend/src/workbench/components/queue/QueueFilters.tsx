import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  DEFAULT_SAVED_VIEWS,
  QUEUE_STATUS_OPTIONS,
  RISK_OPTIONS,
  SLA_OPTIONS,
  TYPE_OPTIONS,
} from '@/workbench/lib/constants';
import { useReviewStore } from '@/workbench/store/useReviewStore';
import type { QueueFilters, SavedView } from '@/workbench/types';

interface OptionItem {
  value: string;
  label: string;
}

/**
 * 判断保存视图是否与当前筛选条件匹配（浅比较视图自身的筛选维度）。
 */
function isViewActive(filters: QueueFilters, view: SavedView): boolean {
  return Object.entries(view.filters).every(([key, value]) => {
    return filters[key as keyof QueueFilters] === value;
  });
}

/** 紧凑筛选下拉 */
function FilterSelect({
  value,
  onValueChange,
  options,
  ariaLabel,
}: {
  value: string;
  onValueChange: (v: string) => void;
  options: OptionItem[];
  ariaLabel: string;
}) {
  return (
    <Select value={value} onValueChange={onValueChange}>
      <SelectTrigger className="h-8 text-xs" aria-label={ariaLabel}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

/** 切换型筛选按钮 */
function ToggleFilter({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <Button
      variant={active ? 'default' : 'outline'}
      size="sm"
      onClick={onClick}
      aria-pressed={active}
    >
      {label}
    </Button>
  );
}

export function QueueFilters() {
  const filters = useReviewStore((s) => s.filters);
  const setFilters = useReviewStore((s) => s.setFilters);
  const applySavedView = useReviewStore((s) => s.applySavedView);

  return (
    <div className="px-3 py-2 border-b border-border space-y-2">
      {/* 保存视图 chips */}
      <div className="flex flex-wrap gap-1">
        {DEFAULT_SAVED_VIEWS.map((view) => (
          <Button
            key={view.id}
            variant={isViewActive(filters, view) ? 'default' : 'outline'}
            size="sm"
            onClick={() => applySavedView(view)}
            aria-pressed={isViewActive(filters, view)}
          >
            {view.name}
          </Button>
        ))}
      </div>

      {/* 筛选下拉（2 列） */}
      <div className="grid grid-cols-2 gap-1.5">
        <FilterSelect
          ariaLabel="状态筛选"
          value={filters.status}
          onValueChange={(v) => setFilters({ status: v })}
          options={QUEUE_STATUS_OPTIONS}
        />
        <FilterSelect
          ariaLabel="风险筛选"
          value={filters.risk}
          onValueChange={(v) => setFilters({ risk: v })}
          options={RISK_OPTIONS}
        />
        <FilterSelect
          ariaLabel="类型筛选"
          value={filters.type}
          onValueChange={(v) => setFilters({ type: v })}
          options={TYPE_OPTIONS}
        />
        <FilterSelect
          ariaLabel="SLA 筛选"
          value={filters.sla}
          onValueChange={(v) => setFilters({ sla: v })}
          options={SLA_OPTIONS}
        />
      </div>

      {/* 切换型筛选 */}
      <div className="flex flex-wrap gap-1">
        <ToggleFilter
          active={filters.validationError}
          onClick={() => setFilters({ validationError: !filters.validationError })}
          label="仅校验异常"
        />
        <ToggleFilter
          active={filters.modified}
          onClick={() => setFilters({ modified: !filters.modified })}
          label="仅已修改"
        />
      </div>
    </div>
  );
}
