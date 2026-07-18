import { useEffect } from 'react';
import { PanelLeft, PanelRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { TooltipProvider } from '@/components/ui/tooltip';
import { WorkbenchHeader } from './components/WorkbenchHeader';
import { ReviewQueue } from './components/queue/ReviewQueue';
import { ReviewWorkspace } from './components/workspace/ReviewWorkspace';
import { ReviewSidebar } from './components/sidebar/ReviewSidebar';
import { StickyDecisionBar } from './components/StickyDecisionBar';
import { ReviewSubmitDialog } from './components/ReviewSubmitDialog';
import { VersionConflictDialog } from './components/VersionConflictDialog';
import { UnsavedSwitchDialog } from './components/UnsavedSwitchDialog';
import { SubmittedToast } from './components/SubmittedToast';
import { useReviewStore } from './store/useReviewStore';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import { useAutoSave } from './hooks/useAutoSave';
import { cn } from '@/lib/utils';

/** 左侧栏收起后的窄轨道 */
function LeftRail() {
  const toggleLeft = useReviewStore((s) => s.toggleLeft);
  return (
    <div className="flex w-12 shrink-0 flex-col items-center border-r border-border bg-background pt-3 max-lg:hidden">
      <Button variant="ghost" size="icon" onClick={toggleLeft} aria-label="展开待审核队列">
        <PanelLeft className="h-4 w-4" />
      </Button>
      <span className="mt-2 text-[10px] text-muted-foreground [writing-mode:vertical-rl]">
        待审核队列
      </span>
    </div>
  );
}

/** 右侧栏收起后的窄轨道 */
function RightRail() {
  const toggleRight = useReviewStore((s) => s.toggleRight);
  return (
    <div className="flex w-12 shrink-0 flex-col items-center border-l border-border bg-background pt-3 max-lg:hidden">
      <Button variant="ghost" size="icon" onClick={toggleRight} aria-label="展开审核控制台">
        <PanelRight className="h-4 w-4" />
      </Button>
      <span className="mt-2 text-[10px] text-muted-foreground [writing-mode:vertical-rl]">
        审核控制台
      </span>
    </div>
  );
}

export function ReviewWorkbench() {
  const init = useReviewStore((s) => s.init);
  const leftCollapsed = useReviewStore((s) => s.leftCollapsed);
  const rightCollapsed = useReviewStore((s) => s.rightCollapsed);
  const toggleLeft = useReviewStore((s) => s.toggleLeft);
  const toggleRight = useReviewStore((s) => s.toggleRight);

  useKeyboardShortcuts();
  useAutoSave();

  useEffect(() => {
    init();
  }, [init]);

  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex h-screen flex-col overflow-hidden bg-app text-foreground">
        <WorkbenchHeader />
        <div className="flex min-h-0 flex-1 relative">
          {/* 左侧队列 — 桌面端内联，移动端覆盖层 */}
          <div
            className={cn(
              'z-30',
              // Desktop: normal inline
              'max-lg:absolute max-lg:inset-y-0 max-lg:left-0 max-lg:z-30 max-lg:shadow-xl max-lg:transition-transform max-lg:duration-200',
              leftCollapsed && 'max-lg:-translate-x-full',
            )}
          >
            {leftCollapsed ? <LeftRail /> : <ReviewQueue />}
          </div>

          {/* 移动端：队列展开时的遮罩 */}
          {!leftCollapsed && (
            <div
              className="hidden max-lg:fixed max-lg:inset-0 max-lg:z-20 max-lg:bg-black/30"
              onClick={toggleLeft}
              aria-hidden
            />
          )}

          <ReviewWorkspace />

          {/* 右侧控制台 — 桌面端内联，移动端覆盖层 */}
          <div
            className={cn(
              'z-30',
              'max-lg:absolute max-lg:inset-y-0 max-lg:right-0 max-lg:z-30 max-lg:shadow-xl max-lg:transition-transform max-lg:duration-200',
              rightCollapsed && 'max-lg:translate-x-full',
            )}
          >
            {rightCollapsed ? <RightRail /> : <ReviewSidebar />}
          </div>

          {/* 移动端：侧栏展开时的遮罩 */}
          {!rightCollapsed && (
            <div
              className="hidden max-lg:fixed max-lg:inset-0 max-lg:z-20 max-lg:bg-black/30"
              onClick={toggleRight}
              aria-hidden
            />
          )}
        </div>
        <StickyDecisionBar />

        {/* 弹窗与提示 */}
        <ReviewSubmitDialog />
        <VersionConflictDialog />
        <UnsavedSwitchDialog />
        <SubmittedToast />
      </div>
    </TooltipProvider>
  );
}