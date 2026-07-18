/**
 * UI Store — 纯展示状态，不涉及业务数据。
 * 从 useReviewStore 拆分出来，可独立使用。
 */
import { create } from 'zustand';
import type { FieldFilter } from '../types';

export interface UIStore {
  density: 'standard' | 'compact';
  leftCollapsed: boolean;
  rightCollapsed: boolean;
  fieldFilter: FieldFilter;
  expandedGroups: Record<string, boolean>;
  editingFieldId: string | null;
  locatingFieldId: string | null;
  locatingTick: number;

  toggleDensity: () => void;
  toggleLeft: () => void;
  toggleRight: () => void;
  setFieldFilter: (filter: FieldFilter) => void;
  toggleGroup: (groupId: string) => void;
  setEditingField: (fieldId: string | null) => void;
  locateField: (fieldId: string) => void;
}

export const useUIStore = create<UIStore>((set, get) => ({
  density: 'standard',
  leftCollapsed: false,
  rightCollapsed: true,
  fieldFilter: 'all',
  expandedGroups: {},
  editingFieldId: null,
  locatingFieldId: null,
  locatingTick: 0,

  toggleDensity: () =>
    set((s) => ({ density: s.density === 'standard' ? 'compact' : 'standard' })),
  toggleLeft: () => set((s) => ({ leftCollapsed: !s.leftCollapsed })),
  toggleRight: () => set((s) => ({ rightCollapsed: !s.rightCollapsed })),
  setFieldFilter: (filter) => set({ fieldFilter: filter }),
  toggleGroup: (groupId) =>
    set((s) => ({ expandedGroups: { ...s.expandedGroups, [groupId]: !s.expandedGroups[groupId] } })),
  setEditingField: (fieldId) => set({ editingFieldId: fieldId }),
  locateField: (fieldId) =>
    set((s) => ({ locatingFieldId: fieldId, locatingTick: s.locatingTick + 1 })),
}));
