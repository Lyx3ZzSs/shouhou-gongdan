import { useEffect, useState } from 'react';
import { AlertTriangle, Ban, CheckCircle2, FileEdit } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { FieldDiff } from './workspace/FieldDiff';
import { useEffectiveChanges, useReviewStore } from '../store/useReviewStore';

export function ReviewSubmitDialog() {
  const open = useReviewStore((s) => s.submitDialogOpen);
  const decision = useReviewStore((s) => s.decision);
  const submitting = useReviewStore((s) => s.submitting);
  const close = useReviewStore((s) => s.closeSubmitDialog);
  const submit = useReviewStore((s) => s.submit);
  const notes = useReviewStore((s) => s.notes);
  const setNotes = useReviewStore((s) => s.setNotes);
  const ticket = useReviewStore((s) => s.ticket);
  const lockState = useReviewStore((s) => s.lockState);
  const changes = useEffectiveChanges();
  const [showReasonError, setShowReasonError] = useState(false);
  const rejected = decision === 'rejected';
  const unchangedApproval = decision === 'approved';
  const lockLost = lockState === 'lost' || lockState === 'error';

  useEffect(() => {
    if (!open) setShowReasonError(false);
  }, [open]);

  if (!decision) return null;

  const confirm = () => {
    if (rejected && !notes.trim()) {
      setShowReasonError(true);
      return;
    }
    void submit(decision, true);
  };

  return (
    <Dialog open={open} onOpenChange={(value) => !value && close()}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {rejected ? <Ban className="h-5 w-5 text-destructive" /> : unchangedApproval ? <CheckCircle2 className="h-5 w-5 text-primary" /> : <FileEdit className="h-5 w-5 text-primary" />}
            {rejected ? '驳回工单' : unchangedApproval ? '确认审核通过' : '确认最终修改'}
          </DialogTitle>
          <DialogDescription>
            {rejected ? '驳回后工单进入“已退回”，必须说明原因。' : unchangedApproval ? '确认关键字段无误并通过该工单。' : '系统只记录本次提交的原值与最终值。'}
          </DialogDescription>
        </DialogHeader>

        {lockLost && (
          <div className="flex gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            <AlertTriangle className="h-4 w-4 shrink-0" />编辑锁已失效，请刷新后重新审核。
          </div>
        )}

        {rejected ? (
          <div>
            <label htmlFor="reject-reason" className="text-sm font-medium">驳回原因 <span className="text-destructive">*</span></label>
            <Textarea
              id="reject-reason"
              autoFocus
              value={notes}
              onChange={(event) => { setNotes(event.target.value); setShowReasonError(false); }}
              placeholder="请输入具体、可执行的驳回原因"
              className="mt-2 min-h-28"
            />
            {showReasonError && <p className="mt-1 text-xs text-destructive" role="alert">必须填写驳回原因</p>}
          </div>
        ) : changes.length > 0 ? (
          <div className="max-h-[55vh] space-y-2 overflow-y-auto">
            {changes.map((change) => {
              const field = ticket?.fields.find((item) => item.id === change.fieldId);
              return (
                <div key={change.fieldId} className="rounded-lg border border-border p-3">
                  <div className="mb-2 text-sm font-medium">{change.fieldName}</div>
                  <FieldDiff before={change.before} after={change.after} field={field} />
                </div>
              );
            })}
          </div>
        ) : null}

        <DialogFooter>
          <Button variant="outline" onClick={close} disabled={submitting}>取消</Button>
          <Button variant={rejected ? 'destructive' : 'default'} onClick={confirm} disabled={submitting || lockLost || (rejected && !notes.trim())} className="gap-2">
            {rejected ? <Ban className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
            {submitting ? '提交中…' : rejected ? '确认驳回' : unchangedApproval ? '确认通过' : '确认修改并通过'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
