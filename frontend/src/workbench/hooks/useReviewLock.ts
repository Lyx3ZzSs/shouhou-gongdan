/**
 * 工作台编辑锁 Hook — 加载工单时获取分布式锁，防止并发编辑冲突。
 *
 * 集成到 ReviewWorkspace 中，当 ticket 加载完成后自动获取锁，
 * 切换工单或卸载时自动释放。
 */

import { useEffect, useRef, useCallback } from 'react';
import { acquireLock, releaseLock, heartbeatLock } from '../../api/review';
import { useReviewStore } from '../store/useReviewStore';

const HEARTBEAT_INTERVAL = 2 * 60 * 1000; // 2 分钟（后端锁 TTL 为 5 分钟）

export function useReviewLock(workorderId: string | undefined) {
  const heartbeatTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const setBeingEditedBy = useReviewStore((s) => s.clearBeingEdited);
  const setLockedBy = useReviewStore((s) => s.triggerBeingEditedDemo);
  // 实际通过 store action 设置，避免直接暴露不安全的 set

  const clearHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current !== null) {
      clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
  }, []);

  // 获取锁
  useEffect(() => {
    if (!workorderId) return;

    let cancelled = false;

    const tryAcquire = async () => {
      try {
        const status = await acquireLock(workorderId);
        if (cancelled) return;

        if (status.locked) {
          // 锁获取成功 — 启动心跳
          useReviewStore.setState({ beingEditedBy: null });
          clearHeartbeat();
          heartbeatTimerRef.current = setInterval(async () => {
            try {
              const result = await heartbeatLock(workorderId);
              if (result === 'lost') {
                useReviewStore.setState({
                  beingEditedBy: '锁已丢失，请刷新页面',
                });
                clearHeartbeat();
              }
            } catch {
              // 心跳失败，下次间隔重试
            }
          }, HEARTBEAT_INTERVAL);
        } else {
          // 锁被他人持有
          useReviewStore.setState({
            beingEditedBy: status.owner ?? '其他用户',
          });
        }
      } catch {
        // 获取锁失败（如 Redis 不可用），静默降级
        useReviewStore.setState({ beingEditedBy: null });
      }
    };

    tryAcquire();

    return () => {
      cancelled = true;
      clearHeartbeat();
      // 释放锁
      releaseLock(workorderId).catch(() => {
        // 锁可能已过期，忽略
      });
    };
  }, [workorderId, clearHeartbeat]);

  // 页面关闭时释放锁（keepalive 确保请求发送）
  useEffect(() => {
    if (!workorderId) return;

    const handleBeforeUnload = () => {
      fetch(`/api/workorders/${workorderId}/lock`, {
        method: 'DELETE',
        keepalive: true,
      });
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [workorderId]);
}
