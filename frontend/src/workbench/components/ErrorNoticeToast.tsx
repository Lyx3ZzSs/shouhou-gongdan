import { useEffect } from 'react';
import { motion } from 'framer-motion';
import { AlertTriangle, X } from 'lucide-react';
import { useReviewStore } from '../store/useReviewStore';
import { toastVariants } from '@/lib/animations';

/** 操作被拦截（如已确认工单禁止编辑）的轻提示，自动消失 */
export function ErrorNoticeToast() {
  const notice = useReviewStore((s) => s.errorNotice);
  const clear = useReviewStore((s) => s.clearErrorNotice);

  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(clear, 2600);
    return () => clearTimeout(t);
  }, [notice, clear]);

  if (!notice) return null;

  return (
        <motion.div
          className="pointer-events-none fixed bottom-20 left-1/2 z-50 -translate-x-1/2"
          variants={toastVariants}
          initial="hidden"
          animate="visible"
        >
          <div className="pointer-events-auto flex items-center gap-2 rounded-2xl border border-warning/30 bg-background/90 backdrop-blur-xl shadow-glass-lg px-4 py-2.5">
            <AlertTriangle className="h-4 w-4 text-warning" />
            <span className="text-sm font-medium">{notice}</span>
            <button
              onClick={clear}
              className="ml-1 rounded-full p-0.5 text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-colors"
              aria-label="关闭提示"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </motion.div>
  );
}
