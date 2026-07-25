import { useState } from 'react';
import { GitCompareArrows, RefreshCw, Trash2, UserCog } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { FieldDiff } from './workspace/FieldDiff';
import { useReviewStore, useEffectiveChanges } from '../store/useReviewStore';

export function VersionConflictDialog() {
  const conflict = useReviewStore((s) => s.conflict);
  const resolveConflict = useReviewStore((s) => s.resolveConflict);
  const ticket = useReviewStore((s) => s.ticket);
  const myChanges = useEffectiveChanges();
  const [showDiff, setShowDiff] = useState(false);

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
            该工单已被 <span className="font-medium text-foreground">{conflict.otherUser}</span> 更新至版本 v{conflict.theirVersion}，请选择如何处理。
          </DialogDescription>
        </DialogHeader>

        {/* 对方修改 */}
        <section>
          <div className="mb-1.5 text-sm font-medium">{conflict.otherUser} 的修改：</div>
          <ul className="space-y-1.5">
            {conflict.theirChanges.map((c, i) => {
              const field = ticket?.fields.find((f) => f.name === c.fieldName);
              return (
                <li key={i} className="flex flex-col gap-0.5">
                  <span className="text-xs text-muted-foreground">{c.fieldName}</span>
                  <FieldDiff before={c.before} after={c.after} field={field} />
                </li>
              );
            })}
          </ul>
        </section>

        {showDiff && (
          <>
            <Separator />
            <section>
              <div className="mb-1.5 text-sm font-medium">双方差异对比：</div>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-md border border-border p-2">
                  <div className="mb-1 flex items-center gap-1 text-xs font-medium text-primary">
                    <Badge variant="default" className="text-[10px]">我</Badge>
                    我的修改（{myChanges.length}）
                  </div>
                  <ul className="space-y-1">
                    {myChanges.length === 0 ? (
                      <li className="text-xs text-muted-foreground">无</li>
                    ) : (
                      myChanges.map((c) => (
                        <li key={c.fieldId} className="text-xs">
                          <span className="text-muted-foreground">{c.fieldName}：</span>
                          <FieldDiff before={c.before} after={c.after} />
                        </li>
                      ))
                    )}
                  </ul>
                </div>
                <div className="rounded-md border border-border p-2">
                  <div className="mb-1 flex items-center gap-1 text-xs font-medium text-warning">
                    <Badge variant="warning" className="text-[10px]">他</Badge>
                    {conflict.otherUser} 的修改
                  </div>
                  <ul className="space-y-1">
                    {conflict.theirChanges.map((c, i) => (
                      <li key={i} className="text-xs">
                        <span className="text-muted-foreground">{c.fieldName}：</span>
                        <FieldDiff before={c.before} after={c.after} />
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </section>
          </>
        )}

        <div className="flex flex-col gap-2">
          <Button onClick={() => resolveConflict('merge')} className="gap-1.5">
            <RefreshCw className="h-4 w-4" />
            使用最新版本并合并（保留我的修改）
          </Button>
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="flex-1 gap-1.5 text-destructive"
              onClick={() => resolveConflict('discard')}
            >
              <Trash2 className="h-4 w-4" />
              放弃我的修改
            </Button>
            <Button
              variant="outline"
              className="flex-1 gap-1.5"
              onClick={() => setShowDiff((v) => !v)}
            >
              <GitCompareArrows className="h-4 w-4" />
              {showDiff ? '收起差异' : '查看双方差异'}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="gap-1 text-muted-foreground"
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
