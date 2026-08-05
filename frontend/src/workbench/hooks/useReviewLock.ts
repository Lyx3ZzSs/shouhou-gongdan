/**
 * 工作台编辑锁 Hook — 加载工单时获取分布式锁，防止并发编辑冲突。
 *
 * 集成到 ReviewWorkspace 中，当 ticket 加载完成后自动获取锁，
 * 切换工单或卸载时自动释放。
 *
 * F2: 锁丢失时设 lockState='lost'，store 中 setFieldValue/submit/stash 全部拦截。
 */

import { useEffect, useRef, useCallback } from 'react';
import { acquireLock, releaseLock, heartbeatLock } from '../../api/review';
import { useReviewStore } from '../store/useReviewStore';

const HEARTBEAT_INTERVAL = 2 * 60 * 1000; // 2 分钟（后端锁 TTL 为 5 分钟）
const MAX_HEARTBEAT_FAILURES = 3; // 连续失败 3 次后判定锁丢失

export function useReviewLock(workorderId: string | undefined) {
  const heartbeatTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
    useReviewStore.setState({ lockState: 'acquiring' });

    const tryAcquire = async () => {
      try {
        const status = await acquireLock(workorderId);
        if (cancelled) return;

        if (status.locked) {
          // 锁获取成功 — 启动心跳
          useReviewStore.setState({ beingEditedBy: null, lockState: 'locked' });
          clearHeartbeat();
          let heartbeatFailures = 0;
          heartbeatTimerRef.current = setInterval(async () => {
            // 提交成功（lockState='released'）或工单已切换/关闭时停掉心跳：
            // 锁已由后端在 confirm 后释放，继续心跳只会收到 423 误报锁丢失。
            const cur = useReviewStore.getState();
            if (cur.lockState === 'released' || !cur.ticket || cur.ticket.id !== workorderId) {
              clearHeartbeat();
              return;
            }
            try {
              const result = await heartbeatLock(workorderId);
              heartbeatFailures = 0; // 成功后重置计数
              if (result === 'lost') {
                useReviewStore.setState({
                  beingEditedBy: '锁已丢失，请刷新页面',
                  lockState: 'lost',
                });
                clearHeartbeat();
              }
            } catch {
              heartbeatFailures += 1;
              if (heartbeatFailures >= MAX_HEARTBEAT_FAILURES) {
                useReviewStore.setState({
                  beingEditedBy: '心跳连接失败，锁可能已丢失',
                  lockState: 'lost',
                });
                clearHeartbeat();
              }
            }
          }, HEARTBEAT_INTERVAL);
        } else {
          // 锁被他人持有
          useReviewStore.setState({
            beingEditedBy: status.owner ?? '其他用户',
            lockState: 'lost',
          });
        }
      } catch {
        // 获取锁失败（如 Redis 不可用），标记为 error 阻止编辑
        useReviewStore.setState({ beingEditedBy: '锁服务不可用', lockState: 'error' });
      }
    };

    tryAcquire();

    return () => {
      cancelled = true;
      clearHeartbeat();
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
