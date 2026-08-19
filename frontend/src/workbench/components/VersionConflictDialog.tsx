import { RefreshCw, Trash2, UserCog } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { FieldDiff } from './workspace/FieldDiff';
import { useReviewStore } from '../store/useReviewStore';

export function VersionConflictDialog() {
  const conflict = useReviewStore((s) => s.conflict);
  const resolveConflict = useReviewStore((s) => s.resolveConflict);
  const ticket = useReviewStore((s) => s.ticket);

  if (!conflict) return null;

  return (
    <Dialog open={!!conflict} onOpenChange={() => {}}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UserCog className="h-5 w-5 text-warning" />
            数据版本冲突
          </DialogTitle>
          <DialogDescription>
            该工单已被 <span className="font-semibold text-warning">{conflict.otherUser}</span> 更新至版本 v{conflict.theirVersion}。为避免覆盖他人结果，只能放弃草稿并重新审核。
          </DialogDescription>
        </DialogHeader>

        {/* 对方修改 */}
        <section>
          <div className="mb-1.5 text-sm font-medium">{conflict.otherUser} 的修改：</div>
          <ul className="space-y-1.5">
            {conflict.theirChanges.map((c, i) => {
              const field = ticket?.fields.find((f) => f.name === c.fieldName);
              return (
                <li key={i} className="flex flex-col gap-0.5 rounded-lg bg-card/40 border border-warning/20 p-2">
                  <span className="text-xs text-muted-foreground">{c.fieldName}</span>
                  <FieldDiff before={c.before} after={c.after} field={field} />
                </li>
              );
            })}
          </ul>
        </section>

        <div className="flex flex-col gap-2">
          <div className="flex gap-2">
            <Button
              variant="destructive"
              className="flex-1 gap-1.5"
              onClick={() => resolveConflict('discard')}
            >
              <Trash2 className="h-4 w-4" />
              放弃草稿并重新审核
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="gap-1 text-muted-foreground rounded-xl"
              onClick={() => window.location.reload()}
            >
              刷新页面
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
