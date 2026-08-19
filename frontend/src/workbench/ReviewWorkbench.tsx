import { useEffect, useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import type { PlatformView } from '@/components/PlatformNav';
import { PlatformNav } from '@/components/PlatformNav';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { TooltipProvider } from '@/components/ui/tooltip';
import { ReviewWorkspace } from './components/workspace/ReviewWorkspace';
import { StickyDecisionBar } from './components/StickyDecisionBar';
import { ReviewSubmitDialog } from './components/ReviewSubmitDialog';
import { VersionConflictDialog } from './components/VersionConflictDialog';
import { UnsavedSwitchDialog } from './components/UnsavedSwitchDialog';
import { SubmittedToast } from './components/SubmittedToast';
import { ErrorNoticeToast } from './components/ErrorNoticeToast';
import { useReviewStore } from './store/useReviewStore';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import { useAutoSave } from './hooks/useAutoSave';
import { ErrorBoundary } from './components/ErrorBoundary';
interface Props {
  onNavigate: (view: PlatformView) => void;
  initialTicketId?: string | null;
  drawer?: boolean;
  onClose?: () => void;
}

export default function ReviewWorkbench({ onNavigate, initialTicketId, drawer = false, onClose }: Props) {
  const init = useReviewStore((s) => s.init);
  const dirty = useReviewStore((s) => s.dirty);
  const stash = useReviewStore((s) => s.stash);
  const discardDraft = useReviewStore((s) => s.discardDraft);
  const [closeConfirmOpen, setCloseConfirmOpen] = useState(false);

  useKeyboardShortcuts();
  useAutoSave();

  useEffect(() => {
    void (async () => {
      await init(initialTicketId ?? undefined);
    })();
  }, [init, initialTicketId]);

  const requestClose = () => {
    if (!onClose) return;
    if (dirty) setCloseConfirmOpen(true);
    else onClose();
  };

  const finishClose = async (action: () => Promise<void>) => {
    await action();
    setCloseConfirmOpen(false);
    onClose?.();
  };

  return (
    <TooltipProvider delayDuration={200}>
      {drawer && <div className="fixed inset-0 z-40 bg-slate-950/10 lg:left-[220px]" aria-hidden="true" />}
      <div
        role={drawer ? 'dialog' : undefined}
        aria-modal={drawer ? true : undefined}
        aria-label={drawer ? '工单审核' : undefined}
        className={drawer
          ? 'fixed inset-y-0 right-0 z-50 flex w-full flex-col overflow-hidden border-l border-border bg-background text-foreground shadow-2xl lg:w-[72vw] lg:min-w-[840px] xl:max-w-[1180px]'
          : 'flex h-screen overflow-hidden bg-app text-foreground'}
      >
        {!drawer && <PlatformNav active="workbench" onNavigate={onNavigate} />}
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          {drawer && (
            <div className="flex h-12 shrink-0 items-center border-b border-border px-5">
              <span className="text-sm font-semibold">工单审核</span>
              <Button variant="ghost" size="icon-sm" className="ml-auto" onClick={requestClose} aria-label="关闭审核抽屉">
                <X className="h-4 w-4" />
              </Button>
            </div>
          )}
          <div className="min-h-0 flex-1 overflow-hidden">
            <ErrorBoundary panelName="工单编辑区" className="h-full"><ReviewWorkspace /></ErrorBoundary>
          </div>
          <ErrorBoundary panelName="审核操作栏"><StickyDecisionBar /></ErrorBoundary>
        </div>

        {/* 弹窗与提示 */}
        <ReviewSubmitDialog />
        <VersionConflictDialog />
        <UnsavedSwitchDialog />
        <SubmittedToast />
        <ErrorNoticeToast />

        <Dialog open={closeConfirmOpen} onOpenChange={setCloseConfirmOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><AlertTriangle className="h-5 w-5 text-warning" />当前工单有未提交修改</DialogTitle>
              <DialogDescription>关闭审核前，请选择保留草稿并稍后处理，或放弃本次修改。</DialogDescription>
            </DialogHeader>
            <DialogFooter className="sm:justify-between">
              <Button variant="ghost" onClick={() => setCloseConfirmOpen(false)}>取消</Button>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => void finishClose(discardDraft)}>放弃修改</Button>
                <Button onClick={() => void finishClose(stash)}>暂存并跳过</Button>
              </div>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </TooltipProvider>
  );
}
