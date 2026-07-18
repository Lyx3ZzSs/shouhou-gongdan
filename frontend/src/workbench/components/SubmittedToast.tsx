import { useEffect } from 'react';
import { CheckCircle2, X } from 'lucide-react';
import { useReviewStore } from '../store/useReviewStore';

/** 提交成功 / 暂存成功的轻提示，自动消失 */
export function SubmittedToast() {
  const toast = useReviewStore((s) => s.submittedToast);
  const clear = useReviewStore((s) => s.clearSubmittedToast);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(clear, 2600);
    return () => clearTimeout(t);
  }, [toast, clear]);

  if (!toast) return null;

  return (
    <div className="pointer-events-none fixed bottom-20 left-1/2 z-50 -translate-x-1/2 animate-fade-in">
      <div className="pointer-events-auto flex items-center gap-2 rounded-md border border-success/30 bg-background px-4 py-2 shadow-lg">
        <CheckCircle2 className="h-4 w-4 text-success" />
        <span className="text-sm">{toast}</span>
        <button
          onClick={clear}
          className="ml-1 text-muted-foreground hover:text-foreground"
          aria-label="关闭提示"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
