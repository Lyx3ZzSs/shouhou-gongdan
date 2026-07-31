import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useReviewStore } from '../store/useReviewStore';

/** 切换工单前存在未保存修改时的确认 */
export function UnsavedSwitchDialog() {
  const pendingSwitchId = useReviewStore((s) => s.pendingSwitchId);
  const confirmSwitch = useReviewStore((s) => s.confirmSwitch);
  const cancelSwitch = useReviewStore((s) => s.cancelSwitch);

  return (
    <Dialog open={!!pendingSwitchId} onOpenChange={(o) => !o && cancelSwitch()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-warning/10 border border-warning/20">
              <AlertTriangle className="h-5 w-5 text-warning" />
            </div>
            切换工单
          </DialogTitle>
          <DialogDescription>
            当前工单存在未保存的修改，切换后将丢失这些修改。确认继续切换吗？
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={cancelSwitch} className="rounded-xl">
            取消
          </Button>
          <Button variant="destructive" onClick={confirmSwitch} className="rounded-xl">
            丢弃修改并切换
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
