import { motion } from 'framer-motion';
import {
  ArrowRight,
  Ban,
  ChevronLeft,
  ChevronRight,
  Save,
  ShieldAlert,
  StepForward,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
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
  const lockState = useReviewStore((s) => s.lockState);
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
  // 已确认/已驳回（提交成功停留当前页）——工单不再可编辑或提交
  const decided = ticket.status === 'confirmed' || ticket.status === 'rejected';

  const handleSubmitClick = () => {
    if (!canSubmit) {
      // 提供显式反馈：滚动到第一个阻断字段
      const first = blockingFields[0];
      if (first) {
        locateField(first.fieldId);
        // 闪烁按钮提示用户
        const btn = document.activeElement as HTMLElement;
        btn?.blur();
      }
      return;
    }
    openSubmitDialog(effectiveChanges.length > 0 ? 'approved_with_changes' : 'approved');
  };

  const blockingHint = !canSubmit && blockingFields.length > 0;

  return (
    <TooltipProvider delayDuration={200}>
      <footer className="flex h-14 shrink-0 items-center justify-between gap-3 border-t border-border/40 bg-background/80 backdrop-blur-xl px-4">
        {/* 左侧：导航 + 暂存 */}
        <div className="flex items-center gap-1.5">
          <Button
            variant="outline"
            size="default"
            className="gap-1.5 rounded-xl"
            onClick={prevTicket}
            disabled={idx <= 0}
          >
            <ChevronLeft className="h-4 w-4" />
            上一条
          </Button>
          <Button
            variant="outline"
            size="default"
            className="gap-1.5 rounded-xl"
            onClick={nextTicket}
            disabled={idx >= list.length - 1}
          >
            下一条
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="default" className="gap-1.5 rounded-xl" onClick={stash}>
            <Save className="h-4 w-4" />
            暂存
            <kbd className="rounded border border-border/50 bg-muted/50 px-1 text-[10px] text-muted-foreground">
              ⌘S
            </kbd>
          </Button>
        </div>

        {/* 右侧：审核结论 */}
        <div className="flex items-center gap-1.5">
          {/* 锁丢失/错误提示 */}
          {(lockState === 'lost' || lockState === 'error') && (
            <button
              onClick={() => window.location.reload()}
              className="inline-flex items-center gap-1.5 rounded-xl bg-destructive/8 backdrop-blur-sm border border-destructive/20 px-2.5 py-1 text-xs font-medium text-destructive hover:bg-destructive/12 transition-colors animate-shake"
            >
              <ShieldAlert className="h-3.5 w-3.5" />
              {lockState === 'error' ? '锁服务不可用，点击刷新页面' : '编辑锁已丢失，点击刷新页面'}
            </button>
          )}
          {blockingHint && (
            <button
              onClick={() => blockingFields[0] && locateField(blockingFields[0].fieldId)}
              className="inline-flex items-center gap-1.5 rounded-xl bg-destructive/8 backdrop-blur-sm border border-destructive/20 px-2.5 py-1 text-xs font-medium text-destructive hover:bg-destructive/12 transition-colors"
              title="定位到第一个阻断字段"
            >
              <ShieldAlert className="h-3.5 w-3.5" />
              存在 {blockingFields.length} 个阻断错误，点击定位
            </button>
          )}

          {decided ? (
            <span className="inline-flex items-center gap-1.5 rounded-xl bg-success/10 border border-success/20 px-2.5 py-1 text-xs font-medium text-success">
              {ticket.status === 'confirmed' ? '已确认提交，等待同步销售易' : '已驳回，工单已退回待审核'}
            </span>
          ) : (
            <>
          <Button
            variant="outline"
            size="default"
            className="gap-1.5 text-destructive border-destructive/20 hover:bg-destructive/8 rounded-xl"
            onClick={() => openSubmitDialog('rejected')}
          >
            <Ban className="h-4 w-4" />
            驳回
          </Button>

          <div className="mx-1 h-6 w-px bg-border/40 rounded-full" />
          </>
          )}

          {/* 主 CTA：确认提交 */}
          {decided ? null : canSubmit && lockState !== 'lost' && lockState !== 'error' ? (
            <motion.div
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
            >
              <Button
                variant="default"
                size="default"
                className="gap-1.5 font-semibold rounded-xl shadow-glow-primary animate-pulse-soft"
                onClick={handleSubmitClick}
              >
                <StepForward className="h-4 w-4" />
                确认提交
                <ArrowRight className="h-4 w-4" />
              </Button>
            </motion.div>
          ) : (
            <Tooltip>
              <TooltipTrigger asChild>
                <span tabIndex={0}>
                  <Button variant="default" size="default" disabled className="gap-1.5 rounded-xl">
                    <StepForward className="h-4 w-4" />
                    确认提交
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent>
                {lockState === 'lost' || lockState === 'error'
                  ? '编辑锁已丢失，请刷新页面'
                  : '存在阻断错误，无法提交'}
              </TooltipContent>
            </Tooltip>
          )}
        </div>
      </footer>
    </TooltipProvider>
  );
}
