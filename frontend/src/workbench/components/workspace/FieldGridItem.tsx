import { useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  HelpCircle,
  KeyRound,
  Lightbulb,
  Pencil,
  RotateCcw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { StatusBadge } from '../primitives/StatusBadge';
import { FieldEditInline } from './FieldEditInline';
import { useReviewStore } from '../../store/useReviewStore';
import { REASON_LABEL } from '../../lib/constants';
import { EMPTY_LABEL, formatValue, isEmpty } from '../../lib/format';
import type { FieldDef } from '../../types';
import { cn } from '@/lib/utils';

/**
 * FieldGridItem — 单个字段在分组卡片内的网格展示。
 *
 * 状态变体：
 * - normal      标签: 值（正常文字）
 * - readonly    标签: 值（灰色文字）
 * - required    标签*: 值（红色星号）
 * - missing     标签*: ⚠ 未填写（红色高亮）
 * - modified    标签: ~~旧值~~ → 新值（删除线 + 高亮背景）
 * - suggestion  标签: 值 + 💡 建议信息
 * - blocking    左侧红色边框 + warning 背景
 */

export function FieldGridItem({
  field,
  columnSpan = 1,
}: {
  field: FieldDef;
  columnSpan?: 1 | 2 | 3;
}) {
  const density = useReviewStore((s) => s.density);
  const fs = useReviewStore((s) => s.fieldStates[field.id]);
  const editingFieldId = useReviewStore((s) => s.editingFieldId);
  const locatingFieldId = useReviewStore((s) => s.locatingFieldId);
  const locatingTick = useReviewStore((s) => s.locatingTick);

  const setEditingField = useReviewStore((s) => s.setEditingField);
  const resetField = useReviewStore((s) => s.resetField);
  const useSuggestion = useReviewStore((s) => s.useSuggestion);
  const ticketStatus = useReviewStore((s) => s.ticket?.status);
  const setErrorNotice = useReviewStore((s) => s.setErrorNotice);

  // 工单已确认/已驳回时字段只读：禁止进入编辑（避免"能进编辑但保存被静默拦截"的死胡同）
  const fieldReadonly = ticketStatus === 'confirmed' || ticketStatus === 'rejected';

  const ref = useRef<HTMLDivElement>(null);
  const [flash, setFlash] = useState(false);

  // 定位闪烁 + 滚动到视图
  useEffect(() => {
    if (locatingFieldId === field.id && ref.current) {
      ref.current.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      setFlash(true);
      const t = setTimeout(() => setFlash(false), 1200);
      return () => clearTimeout(t);
    }
  }, [locatingTick, locatingFieldId, field.id]);

  // null guard must come before any fs property access
  if (!fs) return null;

  const isCompact = density === 'compact';
  const isEditing = editingFieldId === field.id;
  const isModified = fs.status === 'modified';
  // 使用 status 而非 baselineStatus：已修改的阻断字段不应继续显示红色边框
  const isBlocking = !isModified && fs.status === 'blocking_error';
  const isWarning = !isModified && fs.status === 'warning';
  const isReadonly = !!field.readonly;
  const valueIsEmpty = isEmpty(fs.currentValue);
  const isMissing = valueIsEmpty && field.required;

  const currentDisplay = formatValue(fs.currentValue, field);
  const originalDisplay = formatValue(field.originalValue, field);
  const hasSuggestion =
    field.systemSuggestion !== undefined &&
    field.systemSuggestion !== field.originalValue;

  // 列跨
  const colClass =
    columnSpan === 3
      ? 'col-span-3'
      : columnSpan === 2
        ? 'col-span-2'
        : 'col-span-1';

  return (
    <div
      id={`field-${field.id}`}
      ref={ref}
      className={cn(
        'group relative rounded-lg transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50',
        !isReadonly && !fieldReadonly && 'cursor-text hover:bg-accent/10',
        colClass,
        isCompact ? 'px-2 py-1' : 'px-3 py-1.5',
        flash && 'locate-flash ring-2 ring-primary/20',
        isBlocking && 'border border-destructive/30 ring-1 ring-destructive/15 bg-destructive/[0.04] animate-pulse-soft',
        isWarning &&
          !isBlocking &&
          'border border-warning/30 ring-1 ring-warning/15 bg-warning/[0.04]',
        isEditing && 'bg-primary/[0.06] ring-1 ring-primary/20 rounded-xl',
        isModified && 'bg-primary/[0.03] border-l-2 border-primary/30',
      )}
      onDoubleClick={() => {
        if (isReadonly || isEditing) return;
        if (fieldReadonly) {
          setErrorNotice('该工单已确认/已驳回，字段只读，无法修改');
          return;
        }
        setEditingField(field.id);
      }}
      onKeyDown={(e) => {
        if (!isReadonly && !isEditing && (e.key === 'Enter' || e.key === 'F2')) {
          e.preventDefault();
          if (fieldReadonly) {
            setErrorNotice('该工单已确认/已驳回，字段只读，无法修改');
            return;
          }
          setEditingField(field.id);
        }
      }}
      tabIndex={!isReadonly && !isEditing && !fieldReadonly ? 0 : undefined}
      aria-label={!isReadonly && !isEditing && !fieldReadonly ? `编辑 ${field.name}（双击或按 Enter）` : undefined}
    >
      {/* 标签行 */}
      <div className="flex items-start gap-1.5">
        {/* 字段名 */}
        <span
          className={cn(
            'shrink-0 text-xs font-medium tracking-wide',
            isCompact ? 'w-20' : 'w-24',
            isBlocking
              ? 'text-destructive'
              : isWarning
                ? 'text-warning'
                : 'text-muted-foreground',
          )}
        >
          {field.name}
        </span>

        {/* 必填标记 */}
        {field.required && (
          <span className="shrink-0 text-xs text-destructive animate-pulse-soft">●</span>
        )}

        {/* 关键字段图标 */}
        {field.isKey && (
          <Tooltip>
              <TooltipTrigger asChild>
                <KeyRound className="h-3 w-3 shrink-0 text-primary/60" />
              </TooltipTrigger>
              <TooltipContent>关键字段</TooltipContent>
            </Tooltip>
        )}

        {/* 不确定标记 */}
        {fs.uncertain && (
          <Tooltip>
              <TooltipTrigger asChild>
                <HelpCircle className="h-3 w-3 shrink-0 text-warning" />
              </TooltipTrigger>
              <TooltipContent>标记为不确定</TooltipContent>
            </Tooltip>
        )}

        {/* 值区域 */}
        <div className="min-w-0 flex-1">
          {isEditing ? (
            <FieldEditInline field={field} />
          ) : isMissing ? (
            <div className="flex items-center gap-1 text-xs text-destructive">
              <AlertTriangle className="h-3 w-3 shrink-0" />
              <span className="font-medium">未填写</span>
              {field.systemSuggestion !== undefined && (
                <Button
                  variant="link"
                  size="sm"
                  className="h-auto p-0 text-xs text-primary underline"
                  onClick={(e) => { e.stopPropagation(); useSuggestion(field.id); }}
                >
                  使用AI建议: {formatValue(field.systemSuggestion, field)}
                </Button>
              )}
            </div>
          ) : isModified ? (
            <div className="flex flex-col gap-0.5">
              <span className="text-xs" title={`${originalDisplay} → ${currentDisplay}`}>
                <span className="text-muted-foreground line-through">
                  {originalDisplay}
                </span>
                <span className="mx-1 text-muted-foreground">→</span>
                <span className="rounded-sm bg-primary/10 px-1 font-medium text-primary">
                  {currentDisplay}
                </span>
              </span>
              {fs.changeReason && (
                <span className="text-[10px] text-muted-foreground">
                  原因: {REASON_LABEL[fs.changeReason] ?? fs.changeReason}
                </span>
              )}
            </div>
          ) : (
            <span
              className={cn(
                'text-xs',
                isReadonly ? 'text-muted-foreground' : 'text-foreground',
              )}
              title={currentDisplay}
            >
              {currentDisplay === EMPTY_LABEL && !field.required ? (
                <span className="italic">{EMPTY_LABEL}</span>
              ) : (
                currentDisplay
              )}
            </span>
          )}

          {/* 系统建议（非缺失情况下的提示） */}
          {!isEditing && !isMissing && hasSuggestion && (
            <div className="mt-0.5 flex items-center gap-1 text-[10px] text-primary">
              <Lightbulb className="h-3 w-3" />
              <span>
                建议: {formatValue(field.systemSuggestion, field)}
              </span>
              <Button
                variant="link"
                size="sm"
                className="h-auto p-0 text-[10px] text-primary underline"
                onClick={(e) => { e.stopPropagation(); useSuggestion(field.id); }}
              >
                采纳
              </Button>
            </div>
          )}
        </div>

        {/* 状态徽章 */}
        {fs.status !== 'unchecked' && (
          <StatusBadge status={fs.status} />
        )}

        {/* 操作按钮组 — 常驻可见 */}
        {!isEditing && (
          <div className="flex shrink-0 items-center gap-0.5">
            {/* 双击编辑提示 — hover 时以半透明铅笔图标提示可编辑 */}
            {!isReadonly && (
              <Pencil
                className="h-3 w-3 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-25"
                aria-hidden
              />
            )}

            {/* 还原按钮 — 仅已修改字段 */}
            {isModified && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    className="h-5 w-5 text-muted-foreground"
                    onClick={() => resetField(field.id)}
                    onDoubleClick={(e) => e.stopPropagation()}
                    aria-label={`还原 ${field.name}`}
                  >
                    <RotateCcw className="h-3 w-3" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>还原为系统原始值</TooltipContent>
              </Tooltip>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
