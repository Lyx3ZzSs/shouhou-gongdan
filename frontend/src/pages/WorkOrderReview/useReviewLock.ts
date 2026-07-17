import { useEffect, useRef, useCallback } from 'react';
import { message } from 'antd';
import { acquireLock, releaseLock, heartbeatLock } from '../../api/review';
import type { LockStatus } from './types';

const HEARTBEAT_INTERVAL = 2 * 60 * 1000; // 2 minutes

export function useReviewLock(workorderId: string) {
  const lockStatusRef = useRef<LockStatus | null>(null);
  const heartbeatTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current !== null) {
      clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
  }, []);

  const tryAcquire = useCallback(async (): Promise<LockStatus> => {
    const status = await acquireLock(workorderId);
    lockStatusRef.current = status;

    if (status.locked) {
      clearHeartbeat();
      heartbeatTimerRef.current = setInterval(async () => {
        try {
          const result = await heartbeatLock(workorderId);
          if (result === 'lost') {
            message.error('编辑锁已丢失，请刷新页面', 0);
            clearHeartbeat();
          }
        } catch {
          // Heartbeat failed; will retry on next interval
        }
      }, HEARTBEAT_INTERVAL);
    }

    return status;
  }, [workorderId, clearHeartbeat]);

  const tryRelease = useCallback(async () => {
    clearHeartbeat();
    try {
      await releaseLock(workorderId);
    } catch {
      // Lock may have already expired; ignore
    }
  }, [workorderId, clearHeartbeat]);

  // Cleanup heartbeat timer on unmount
  useEffect(() => {
    return () => {
      clearHeartbeat();
    };
  }, [clearHeartbeat]);

  // Release lock on page close using fetch keepalive for guaranteed delivery
  useEffect(() => {
    const handleBeforeUnload = () => {
      // keepalive ensures the request completes even after the page unloads
      fetch(`/api/workorders/${workorderId}/lock`, {
        method: 'DELETE',
        keepalive: true,
      });
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [workorderId]);

  return { lockStatusRef, tryAcquire, tryRelease };
}
