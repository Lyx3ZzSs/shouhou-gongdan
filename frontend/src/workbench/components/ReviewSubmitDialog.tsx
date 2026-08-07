import { useState, useEffect } from 'react';
import { AlertTriangle, CheckCircle2, FileEdit, ListChecks } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Separator } from '@/components/ui/separator';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { FieldDiff } from './workspace/FieldDiff';
import {
  useReviewStore,
  useEffectiveChanges,
  useReviewProgress,
  useUnresolvedAnomalies,
} from '../store/useReviewStore';
import { DECISION_META, REASON_LABEL } from '../lib/constants';

export function ReviewSubmitDialog() {
  const open = useReviewStore((s) => s.submitDialogOpen);
  const decision = useReviewStore((s) => s.decision);
  const submitting = useReviewStore((s) => s.submitting);
  const closeSubmitDialog = useReviewStore((s) => s.closeSubmitDialog);
  const submit = useReviewStore((s) => s.submit);
  const notes = useReviewStore((s) => s.notes);
  const setNotes = useReviewStore((s) => s.setNotes);
  const ticket = useReviewStore((s) => s.ticket);
  const lockState = useReviewStore((s) => s.lockState);

  const changes = useEffectiveChanges();
  const progress = useReviewProgress();
  const unresolved = useUnresolvedAnomalies();
  const [openNext, setOpenNext] = useState(false);
  const [showNotesError, setShowNotesError] = useState(false);

  useEffect(() => {
    setShowNotesError(false);
  }, [decision]);
  useEffect(() => {
    if (open) setShowNotesError(false);
  }, [open]);
  useEffect(() => {
    if (notes?.trim()) {
      setShowNotesError(false);
    }
  }, [notes]);

  if (!decision) return null;

  const meta = DECISION_META[decision];
  const totalAnomalies = ticket?.anomalies.length ?? 0;
  const handled = totalAnomalies - unresolved.length;

  const handleSubmit = () => {
    if (lockState === 'lost' || lockState === 'error') {
      return; // 锁已丢失，submit() 内部也会拦截并设置 error
    }
    if (decision === 'rejected' && !notes?.trim()) {
      setShowNotesError(true);
      return;
    }
    setShowNotesError(false);
    submit(decision, openNext);
  };

  const lockLost = lockState === 'lost' || lockState === 'error';

  const reasonSummary = new Map<string, number>();
  for (const c of changes) {
    reasonSummary.set(c.reason, (reasonSummary.get(c.reason) ?? 0) + 1);
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && closeSubmitDialog()}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            确认提交
            <Badge variant={meta.variant}>{meta.label}</Badge>
          </DialogTitle>
          <DialogDescription>确认后工单将同步至销售易系统，可在队列中查看同步状态。</DialogDescription>
        </DialogHeader>

        <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-1">
          {/* 锁丢失警告 */}
          {lockLost && (
            <section className="flex items-start gap-2 rounded-lg bg-destructive/8 border border-destructive/20 p-3 text-sm text-destructive">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <p className="font-medium">编辑锁已丢失</p>
                <p className="text-xs text-destructive/70 mt-0.5">
                  编辑锁已过期或被释放，无法提交审核。请刷新页面重新获取编辑锁后再操作。
                </p>
              </div>
            </section>
          )}
          {/* 本次修改 */}
          <section>
            <div className="mb-1.5 flex items-center gap-1.5 text-sm font-medium">
              <FileEdit className="h-4 w-4 text-primary" />
              本次共修改 {changes.length} 个字段
            </div>
            {changes.length === 0 ? (
              <p className="text-xs text-muted-foreground">未修改任何字段。</p>
            ) : (
              <ul className="space-y-1.5">
                {changes.map((c) => {
                  const field = ticket?.fields.find((f) => f.id === c.fieldId);
                  return (
                    <li key={c.fieldId} className="flex flex-col gap-0.5 rounded-lg bg-card/40 border border-border/20 p-2">
                      <span className="text-xs text-muted-foreground">{c.fieldName}</span>
                      <FieldDiff before={c.before} after={c.after} field={field} />
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <Separator />

          {/* 异常处理情况 */}
          <section>
            <div className="mb-1.5 flex items-center gap-1.5 text-sm font-medium">
              <ListChecks className="h-4 w-4 text-success" />
              已处理 {handled} / {totalAnomalies} 个问题
            </div>
            {unresolved.length > 0 && (
              <div className="space-y-1">
                <p className="text-xs font-medium text-destructive">尚未处理的问题：</p>
                <ul className="space-y-0.5">
                  {unresolved.map((a) => (
                    <li key={a.id} className="flex items-start gap-1.5 text-xs text-muted-foreground rounded-lg bg-warning/[0.04] border-l-2 border-warning/40 p-2">
                      <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-warning" />
                      {a.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {unresolved.length === 0 && (
              <div className="flex items-center gap-1.5 rounded-lg bg-success/5 p-2 text-xs text-success">
                <CheckCircle2 className="h-3.5 w-3.5" />
                所有问题均已处理
              </div>
            )}
          </section>

          <Separator />

          {/* 修改原因汇总 */}
          {reasonSummary.size > 0 && (
            <>
              <section>
                <div className="mb-1.5 text-sm font-medium">修改原因汇总</div>
                <div className="flex flex-wrap gap-1.5">
                  {[...reasonSummary.entries()].map(([reason, count]) => (
                    <Badge key={reason} variant="secondary" className="gap-1">
                      {REASON_LABEL[reason] ?? reason}
                      <span className="text-muted-foreground">×{count}</span>
                    </Badge>
                  ))}
                </div>
              </section>
              <Separator />
            </>
          )}

          {/* 审核备注 */}
          <section>
            <div className="mb-1.5 text-sm font-medium">
              审核备注
              {decision === 'rejected' && <span className="text-destructive ml-0.5">*</span>}
            </div>
            <Textarea
              value={notes}
              onChange={(e) => {
                setNotes(e.target.value);
                if (showNotesError && e.target.value.trim()) {
                  setShowNotesError(false);
                }
              }}
              placeholder={decision === 'rejected' ? '驳回时必须填写审核备注…' : '填写审核备注…'}
              className={`min-h-[64px] ${showNotesError ? 'border-destructive ring-1 ring-destructive/20' : ''}`}
            />
            {showNotesError && (
              <p className="mt-1 text-xs text-destructive">驳回时必须填写审核备注</p>
            )}
          </section>

          {/* 进度摘要 */}
          <section className="rounded-xl bg-muted/30 backdrop-blur-sm p-2.5 text-xs text-muted-foreground">
            审核进度 {progress.confirmed + progress.modified} / {progress.total}，已确认 {progress.confirmed}，已修改 {progress.modified}，待处理异常 {progress.pendingAnomalies}。
          </section>
        </div>

        <DialogFooter className="flex items-center justify-between sm:justify-between">
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
            <input
              type="checkbox"
              checked={openNext}
              onChange={(e) => setOpenNext(e.target.checked)}
              className="h-3.5 w-3.5 rounded border-border accent-primary"
            />
            提交并进入下一条
          </label>
          <div className="flex gap-2">
            <Button variant="outline" onClick={closeSubmitDialog} disabled={submitting} className="rounded-xl">
              取消
            </Button>
            <Button onClick={handleSubmit} disabled={submitting || lockLost} className="rounded-xl shadow-glow-primary">
              {lockLost ? '请刷新页面' : submitting ? '提交中…' : `提交（${meta.label}）`}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
