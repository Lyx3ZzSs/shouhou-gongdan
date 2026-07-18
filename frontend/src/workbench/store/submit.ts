/**
 * Submit Store — 提交/确认审核的 UI 状态。
 * 从 useReviewStore 拆分出来，可独立使用。
 */
import { create } from 'zustand';
import type { ReviewDecision } from '../types';

export interface SubmitStore {
  decision: ReviewDecision | null;
  submitDialogOpen: boolean;
  submitting: boolean;
  submittedToast: string | null;
  queueEmpty: boolean;

  openSubmitDialog: (decision: ReviewDecision) => void;
  closeSubmitDialog: () => void;
  clearSubmittedToast: () => void;
}

export const useSubmitStore = create<SubmitStore>((set) => ({
  decision: null,
  submitDialogOpen: false,
  submitting: false,
  submittedToast: null,
  queueEmpty: false,

  openSubmitDialog: (decision) => set({ submitDialogOpen: true, decision }),
  closeSubmitDialog: () => set({ submitDialogOpen: false, submitting: false }),
  clearSubmittedToast: () => set({ submittedToast: null }),
}));
