import { Ban, CheckCircle2, Save, ShieldAlert } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useCanSubmit, useEffectiveChanges, useReviewStore } from '../store/useReviewStore';

export function StickyDecisionBar() {
  const ticket = useReviewStore((s) => s.ticket);
  const lockState = useReviewStore((s) => s.lockState);
  const saveDraft = useReviewStore((s) => s.saveDraft);
  const openSubmitDialog = useReviewStore((s) => s.openSubmitDialog);
  const changes = useEffectiveChanges();
  const canSubmit = useCanSubmit();

  if (!ticket) return null;
  const readonly = ticket.status === 'confirmed' || ticket.status === 'rejected';
  const lockLost = lockState === 'lost' || lockState === 'error';

  const approve = () => {
    if (!canSubmit || lockLost) return;
    openSubmitDialog(changes.length === 0 ? 'approved' : 'approved_with_changes');
  };

  return (
    <footer className="flex min-h-[72px] shrink-0 flex-wrap items-center gap-3 border-t border-border bg-background px-5 py-3 lg:px-8">
        <div className="mr-auto text-sm">
          {changes.length > 0 ? (
            <span className="font-medium text-primary">已修改 {changes.length} 个字段，提交前将复核最终 Diff</span>
          ) : (
            <span className="text-muted-foreground">未修改字段，可直接审核通过</span>
          )}
          {lockLost && <span className="ml-3 inline-flex items-center gap-1 text-destructive"><ShieldAlert className="h-4 w-4" />编辑锁已失效</span>}
        </div>
        {!readonly && (
          <>
            <Button variant="outline" onClick={() => void saveDraft()} disabled={lockLost} className="gap-2">
              <Save className="h-4 w-4" />暂存 <kbd className="text-xs text-muted-foreground">⌘S</kbd>
            </Button>
            <Button variant="outline" onClick={() => openSubmitDialog('rejected')} disabled={lockLost} className="gap-2 border-destructive/40 text-destructive hover:bg-destructive/5">
              <Ban className="h-4 w-4" />驳回
            </Button>
            <Button onClick={approve} disabled={!canSubmit || lockLost} className="gap-2 px-5">
              <CheckCircle2 className="h-4 w-4" />审核通过 <kbd className="text-xs opacity-75">⌘Enter</kbd>
            </Button>
          </>
        )}
    </footer>
  );
}
