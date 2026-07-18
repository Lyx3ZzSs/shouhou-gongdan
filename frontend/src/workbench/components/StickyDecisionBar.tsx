import {
  ArrowRight,
  Ban,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Save,
  Share2,
  ShieldAlert,
  StepForward,
  Undo2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  useReviewStore,
  useCanSubmit,
  useBlockingFields,
  useEffectiveChanges,
  useFilteredQueue,
} from '../store/useReviewStore';

export function StickyDecisionBar() {
  const ticket = useReviewStore((s) => s.ticket);
  const prevTicket = useReviewStore((s) => s.prevTicket);
  const nextTicket = useReviewStore((s) => s.nextTicket);
  const stash = useReviewStore((s) => s.stash);
  const openSubmitDialog = useReviewStore((s) => s.openSubmitDialog);
  const locateField = useReviewStore((s) => s.locateField);
  const selectedId = useReviewStore((s) => s.selectedId);
  const list = useFilteredQueue();

  const canSubmit = useCanSubmit();
  const blockingFields = useBlockingFields();
  const effectiveChanges = useEffectiveChanges();

  if (!ticket) return null;

  const idx = list.findIndex((i) => i.id === selectedId);

  const handleSubmitClick = () => {
    if (!canSubmit) {
      const first = blockingFields[0];
      if (first) locateField(first.fieldId);
      return;
    }
    // 有修改时自动使用 "修改后通过"，无修改时使用 "直接通过"
    openSubmitDialog(effectiveChanges.length > 0 ? 'approved_with_changes' : 'approved');
  };

  const blockingHint = !canSubmit && blockingFields.length > 0;

  return (
    <TooltipProvider delayDuration={200}>
      <footer className="flex h-14 shrink-0 items-center justify-between gap-3 border-t border-border bg-background px-4">
        {/* 左侧：导航 + 暂存 */}
        <div className="flex items-center gap-1.5">
          <Button
            variant="outline"
            size="default"
            className="gap-1.5"
            onClick={prevTicket}
            disabled={idx <= 0}
          >
            <ChevronLeft className="h-4 w-4" />
            上一条
          </Button>
          <Button
            variant="outline"
            size="default"
            className="gap-1.5"
            onClick={nextTicket}
            disabled={idx >= list.length - 1}
          >
            下一条
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="default" className="gap-1.5" onClick={stash}>
            <Save className="h-4 w-4" />
            暂存
            <kbd className="rounded border border-border bg-muted px-1 text-[10px] text-muted-foreground">
              ⌘S
            </kbd>
          </Button>
        </div>

        {/* 右侧：审核结论 */}
        <div className="flex items-center gap-1.5">
          {blockingHint && (
            <button
              onClick={() => blockingFields[0] && locateField(blockingFields[0].fieldId)}
              className="inline-flex items-center gap-1.5 rounded-md bg-destructive/10 px-2 py-1 text-xs font-medium text-destructive hover:bg-destructive/15"
              title="定位到第一个阻断字段"
            >
              <ShieldAlert className="h-3.5 w-3.5" />
              存在 {blockingFields.length} 个阻断错误，点击定位
            </button>
          )}

          <Button
            variant="outline"
            size="default"
            className="gap-1.5 text-warning"
            onClick={() => openSubmitDialog('returned')}
          >
            <Undo2 className="h-4 w-4" />
            退回补充
          </Button>
          <Button
            variant="outline"
            size="default"
            className="gap-1.5 text-destructive"
            onClick={() => openSubmitDialog('rejected')}
          >
            <Ban className="h-4 w-4" />
            驳回
          </Button>

          {/* 更多操作下拉 */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="default" className="gap-1">
                更多
                <ChevronDown className="h-3.5 w-3.5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-36">
              <DropdownMenuItem onClick={() => openSubmitDialog('transferred')}>
                <Share2 className="h-4 w-4" />
                转交复核
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <div className="mx-1 h-6 w-px bg-border" />

          {/* 主 CTA：提交审核 */}
          {canSubmit ? (
            <Button
              variant="default"
              size="default"
              className="gap-1.5 font-semibold"
              onClick={handleSubmitClick}
            >
              <StepForward className="h-4 w-4" />
              提交审核
              <ArrowRight className="h-4 w-4" />
            </Button>
          ) : (
            <Tooltip>
              <TooltipTrigger asChild>
                <span tabIndex={0}>
                  <Button variant="default" size="default" disabled className="gap-1.5">
                    <StepForward className="h-4 w-4" />
                    提交审核
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent>存在阻断错误，无法提交</TooltipContent>
            </Tooltip>
          )}
        </div>
      </footer>
    </TooltipProvider>
  );
}