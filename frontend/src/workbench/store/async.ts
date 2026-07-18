/**
 * Async Store — 异步加载状态 + 并发控制。
 * 从 useReviewStore 拆分出来，可独立使用。
 */
import { create } from 'zustand';
import type { AutoSaveStatus, ConflictInfo } from '../types';

export interface AsyncStore {
  queueLoading: boolean;
  ticketLoading: boolean;
  error: string | null;
  sessionId: string;
  autoSaveStatus: AutoSaveStatus;
  conflict: ConflictInfo | null;
  beingEditedBy: string | null;
  lockState: 'acquiring' | 'locked' | 'lost';
  dirty: boolean;
  pendingSwitchId: string | null;
  currentLoadId: number;

  setLockState: (s: 'acquiring' | 'locked' | 'lost') => void;
  setAutoSaveStatus: (s: AutoSaveStatus) => void;
}

export const useAsyncStore = create<AsyncStore>((set) => ({
  queueLoading: false,
  ticketLoading: false,
  error: null,
  sessionId: '',
  autoSaveStatus: 'idle',
  conflict: null,
  beingEditedBy: null,
  lockState: 'acquiring',
  dirty: false,
  pendingSwitchId: null,
  currentLoadId: 0,

  setLockState: (s) => set({ lockState: s }),
  setAutoSaveStatus: (s) => set({ autoSaveStatus: s }),
}));
