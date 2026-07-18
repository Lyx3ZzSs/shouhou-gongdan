import { useEffect, useRef } from 'react';
import { useReviewStore } from '../store/useReviewStore';
import { stashWorkOrder } from '../../api/review';

/**
 * 自动暂存（spec 第八节）：
 * - dirty 后 1s 发起真实 POST /api/workorders/{id}/stash
 * - 成功后设 autoSaveStatus='saved'，失败降级为 'failed'
 * - 定时保存（每 30s，若仍有未保存修改）
 */
export function useAutoSave() {
  const dirty = useReviewStore((s) => s.dirty);
  const autoSaveStatus = useReviewStore((s) => s.autoSaveStatus);
  const setAutoSaveStatus = useReviewStore((s) => s.setAutoSaveStatus);
  const ticketId = useReviewStore((s) => s.ticket?.id);

  const dirtyRef = useRef(dirty);
  dirtyRef.current = dirty;
  const ticketRef = useRef(ticketId);
  ticketRef.current = ticketId;

  // dirty + 'saving' → 1s 后发起真实 stash API 调用
  useEffect(() => {
    if (!dirty || autoSaveStatus !== 'saving' || !ticketId) return;
    const t = setTimeout(async () => {
      try {
        const store = useReviewStore.getState();
        const fieldStates = Object.fromEntries(
          Object.entries(store.fieldStates).map(([id, fs]) => [
            id,
            { currentValue: fs.currentValue, status: fs.status, changeReason: fs.changeReason },
          ]),
        );
        await stashWorkOrder(ticketId, fieldStates, store.notes);
        setAutoSaveStatus('saved');
      } catch {
        setAutoSaveStatus('failed');
      }
    }, 1000);
    return () => clearTimeout(t);
  }, [dirty, autoSaveStatus, setAutoSaveStatus, ticketId]);

  // 定时保存：仍有未保存修改时周期性触发保存中
  useEffect(() => {
    const t = setInterval(() => {
      if (dirtyRef.current && ticketRef.current) {
        const status = useReviewStore.getState().autoSaveStatus;
        if (status !== 'saving' && status !== 'failed') {
          setAutoSaveStatus('saving');
        }
      }
    }, 30000);
    return () => clearInterval(t);
  }, [setAutoSaveStatus]);
}
