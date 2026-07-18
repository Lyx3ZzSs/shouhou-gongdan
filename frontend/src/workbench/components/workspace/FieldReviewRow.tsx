import { useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  HelpCircle,
  History,
  KeyRound,
  Lightbulb,
  MessageSquare,
  Pencil,
  RotateCcw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Separator } from '@/components/ui/separator';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { StatusBadge } from '../primitives/StatusBadge';
import { FieldDiff } from './FieldDiff';
import { FieldEditInline } from './FieldEditInline';
import { useReviewStore } from '../../store/useReviewStore';
import { REASON_LABEL } from '../../lib/constants';
import { EMPTY_LABEL, formatValue, formatTime } from '../../lib/format';
import type { FieldDef } from '../../types';
import { cn } from '@/lib/utils';

function anomalyBarColor(status: string | undefined): string {
  switch (status) {
    case 'blocking_error':
      return 'bg-destructive';
    case 'warning':
      return 'bg-warning';
    default:
      return 'bg-transparent';
  }
}

export function FieldReviewRow({ field, index }: { field: FieldDef; index: number }) {
  const density = useReviewStore((s) => s.density);
  const isCompact = density === 'compact';
  const fs = useReviewStore((s) => s.fieldStates[field.id]);
  const editingFieldId = useReviewStore((s) => s.editingFieldId);
  const locatingFieldId = useReviewStore((s) => s.locatingFieldId);
  const locatingTick = useReviewStore((s) => s.locatingTick);
  const changeLog = useReviewStore((s) => s.changeLog);

  const setEditingField = useReviewStore((s) => s.setEditingField);
  const resetField = useReviewStore((s) => s.resetField);
  const useSuggestion = useReviewStore((s) => s.useSuggestion);
  const setFieldRemark = useReviewStore((s) => s.setFieldRemark);
  const toggleUncertain = useReviewStore((s) => s.toggleUncertain);

  const ref = useRef<HTMLDivElement>(null);
  const [flash, setFlash] = useState(false);

  const isEditing = editingFieldId === field.id;
  const isModified = fs?.status === 'modified';
  const isReadonly = !!field.readonly;
  const fieldHistory = changeLog.filter((c) => c.fieldId === field.id);
  const hasAnomaly = fs?.baselineStatus !== 'unchecked';

  useEffect(() => {
    if (locatingFieldId === field.id && ref.current) {
      ref.current.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      setFlash(true);
      const t = setTimeout(() => setFlash(false), 1200);
      return () => clearTimeout(t);
    }
  }, [locatingTick, locatingFieldId, field.id]);

  if (!fs) return null;

  const currentDisplay = formatValue(fs.currentValue, field);
  const originalDisplay = formatValue(field.originalValue, field);
  const isMissing = fs.currentValue === '' || fs.currentValue == null;

  // ---- Diff-style value column ----
  const renderValueCell = () => {
    if (isEditing) return <FieldEditInline field={field} />;

    if (isModified) {
      return (
        <div className="min-w-0 truncate text-sm" title={`${originalDisplay} → ${currentDisplay}`}>
          <span className="text-muted-foreground line-through">{originalDisplay}</span>
          <span className="mx-1 text-muted-foreground">→</span>
          <span className="rounded-sm bg-primary/10 px-1 text-foreground">{currentDisplay}</span>
        </div>
      );
    }

    if (isMissing && field.required) {
      return (
        <div className="flex items-center gap-1 text-sm text-destructive">
          <AlertTriangle className="h-3.5 w-3.5" />
          未填写
        </div>
      );
    }

    return (
      <div className="min-w-0 truncate text-sm" title={currentDisplay}>
        <span className={cn(isReadonly ? 'text-muted-foreground' : 'text-foreground')}>
          {currentDisplay}
        </span>
      </div>
    );
  };

  return (
    <div
      ref={ref}
      className={cn(
        'group grid grid-cols-[3px_140px_minmax(0,1fr)_90px_auto] max-lg:grid-cols-[3px_100px_minmax(0,1fr)_auto] items-center gap-x-3 transition-colors',
        isCompact ? 'px-3 py-1 text-xs' : 'px-4 py-2 text-sm',
        // Zebra striping
        index % 2 === 0 ? 'bg-transparent' : 'bg-muted/[0.25]',
        flash && 'locate-flash',
        isEditing && 'bg-primary/[0.04]',
        hasAnomaly && 'bg-destructive/[0.03]',
      )}
    >
      {/* 异常左侧色条 */}
      <div className={cn('h-full w-[3px] rounded-full', anomalyBarColor(fs?.baselineStatus))} />

      {/* 字段名 */}
      <div className="flex items-center gap-1 min-w-0">
        <span className="truncate text-sm font-medium" title={field.name}>
          {field.name}
        </span>
        {field.required && <span className="text-destructive">*</span>}
        {field.isKey && (
          <KeyRound className="h-3 w-3 shrink-0 text-muted-foreground" aria-label="关键字段" />
        )}
        {fs.uncertain && (
          <HelpCircle className="h-3 w-3 shrink-0 text-warning" aria-label="标记为不确定" />
        )}
      </div>

      {/* 值（diff 视图）/ 编辑 */}
      {renderValueCell()}

      {/* 状态 — 小屏隐藏；unchecked 不展示，减少视觉噪音 */}
      <div className="flex flex-wrap items-center gap-1 max-lg:hidden">
        {fs.status !== 'unchecked' && <StatusBadge status={fs.status} />}
        {fs.uncertain && <Badge variant="muted" className="text-[10px]">不确定</Badge>}
      </div>

      {/* 操作 — hover 时显示 */}
      <div className="flex items-center justify-end gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
        <TooltipProvider delayDuration={300}>
          {!isReadonly && !isEditing && (
            <>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => setEditingField(field.id)}
                    aria-label={`编辑 ${field.name}`}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>编辑</TooltipContent>
              </Tooltip>

              {isModified && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => resetField(field.id)}
                      aria-label={`重置 ${field.name} 为系统原始值`}
                    >
                      <RotateCcw className="h-3.5 w-3.5" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>重置为系统原始值</TooltipContent>
                </Tooltip>
              )}

              {field.systemSuggestion !== undefined && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => useSuggestion(field.id)}
                      aria-label={`使用系统建议值`}
                    >
                      <Lightbulb className="h-3.5 w-3.5 text-primary" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>使用系统建议值：{formatValue(field.systemSuggestion, field)}</TooltipContent>
                </Tooltip>
              )}
            </>
          )}

          {/* 更多：历史 / 备注 / 标记不确定 */}
          {!isEditing && (
            <DropdownMenu>
              <Tooltip>
                <TooltipTrigger asChild>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon-sm" aria-label="更多操作">
                      <MessageSquare className="h-3.5 w-3.5 rotate-90" />
                    </Button>
                  </DropdownMenuTrigger>
                </TooltipTrigger>
                <TooltipContent>更多操作</TooltipContent>
              </Tooltip>
              <DropdownMenuContent align="end" className="w-44">
                <Popover>
                  <PopoverTrigger asChild>
                    <DropdownMenuItem onSelect={(e) => e.preventDefault()}>
                      <History className="h-4 w-4" />
                      查看修改历史
                      {fieldHistory.length > 0 && (
                        <span className="ml-auto text-xs text-muted-foreground">
                          {fieldHistory.length}
                        </span>
                      )}
                    </DropdownMenuItem>
                  </PopoverTrigger>
                  <PopoverContent align="end" className="w-80">
                    <div className="mb-2 text-xs font-medium text-muted-foreground">
                      {field.name} · 修改历史
                    </div>
                    {fieldHistory.length === 0 ? (
                      <div className="py-4 text-center text-xs text-muted-foreground">
                        暂无修改记录
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {fieldHistory.map((c) => (
                          <div key={c.id} className="space-y-1">
                            <div className="flex items-center justify-between text-xs text-muted-foreground">
                              <span>{formatTime(c.timestamp)}</span>
                              <span>{REASON_LABEL[c.reason] ?? c.reason}</span>
                            </div>
                            <FieldDiff before={c.before} after={c.after} field={field} />
                            <Separator />
                          </div>
                        ))}
                      </div>
                    )}
                  </PopoverContent>
                </Popover>

                <Popover>
                  <PopoverTrigger asChild>
                    <DropdownMenuItem onSelect={(e) => e.preventDefault()}>
                      <MessageSquare className="h-4 w-4" />
                      添加字段备注
                      {fs.remark && <span className="ml-auto text-xs text-primary">已备注</span>}
                    </DropdownMenuItem>
                  </PopoverTrigger>
                  <PopoverContent align="end" className="w-72">
                    <div className="mb-2 text-xs font-medium text-muted-foreground">
                      {field.name} · 备注
                    </div>
                    <Textarea
                      value={fs.remark ?? ''}
                      onChange={(e) => setFieldRemark(field.id, e.target.value)}
                      placeholder="填写该字段的审核备注…"
                      className="min-h-[60px]"
                    />
                  </PopoverContent>
                </Popover>

                <DropdownMenuItem onClick={() => toggleUncertain(field.id)}>
                  <HelpCircle className="h-4 w-4" />
                  {fs.uncertain ? '取消不确定标记' : '标记为不确定'}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </TooltipProvider>
      </div>
    </div>
  );
}