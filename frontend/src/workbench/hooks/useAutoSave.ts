import { useEffect, useRef } from 'react';
import { useReviewStore } from '../store/useReviewStore';

/**
 * 自动暂存（spec 第八节）：
 * - 字段失焦 / 停止输入约 1s -> 保存中 -> 已自动保存
 * - 定时保存（每 30s，若仍有未保存修改）
 * 离线 / 失败状态通过"更多操作 -> 模拟"显式触发演示。
 */
export function useAutoSave() {
  const dirty = useReviewStore((s) => s.dirty);
  const autoSaveStatus = useReviewStore((s) => s.autoSaveStatus);
  const setAutoSaveStatus = useReviewStore((s) => s.setAutoSaveStatus);

  const dirtyRef = useRef(dirty);
  dirtyRef.current = dirty;
  const statusRef = useRef(autoSaveStatus);
  statusRef.current = autoSaveStatus;

  // 停止输入约 1s 后标记为已保存
  useEffect(() => {
    if (!dirty || autoSaveStatus !== 'saving') return;
    const t = setTimeout(() => setAutoSaveStatus('saved'), 1000);
    return () => clearTimeout(t);
  }, [dirty, autoSaveStatus, setAutoSaveStatus]);

  // 定时保存：仍有未保存修改时周期性触发保存中
  useEffect(() => {
    const t = setInterval(() => {
      if (dirtyRef.current && statusRef.current !== 'saving') {
        setAutoSaveStatus('saving');
      }
    }, 30000);
    return () => clearInterval(t);
  }, [setAutoSaveStatus]);
}
