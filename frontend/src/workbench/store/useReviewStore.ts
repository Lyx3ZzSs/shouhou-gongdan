import { useMemo } from 'react';
import { create } from 'zustand';
import { useShallow } from 'zustand/react/shallow';
import type {
  Anomaly,
  AutoSaveStatus,
  ChangeRecord,
  ConflictInfo,
  EffectiveChange,
  FieldDef,
  FieldFilter,
  FieldReviewStatus,
  FieldState,
  QueueFilters,
  QueueItem,
  ReviewDecision,
  ReviewProgress,
  ReviewTicket,
  SavedView,
} from '../types';
import {
  DEFAULT_SAVED_VIEWS,
  LOW_CONFIDENCE_THRESHOLD,
} from '../lib/constants';
import { nowIso, valuesEqual } from '../lib/format';
import { CONFLICT_DEMO } from '../mock/mockData';
import {
  fetchWorkOrderList,
  fetchWorkOrder,
  fetchAuditLogs,
  submitReview,
  ConflictError,
} from '../../api/review';
import {
  workOrderSummaryToQueueItem,
  workOrderDataToReviewTicket,
  auditLogSessionsToEntries,
  changeRecordToFieldChange,
} from '../lib/converters';

let _uid = 0;
function uid(prefix = 'id'): string {
  _uid += 1;
  return `${prefix}-${_uid}`;
}

// ---------------------------------------------------------------------------
// 纯函数：派生计算
// ---------------------------------------------------------------------------

function computeBaseline(field: FieldDef, anomalies: Anomaly[]): FieldReviewStatus {
  const linked = anomalies.filter((a) => a.fieldId === field.id);
  if (linked.some((a) => a.type === 'blocking_error')) return 'blocking_error';
  if (field.confidence != null && field.confidence < LOW_CONFIDENCE_THRESHOLD) return 'low_confidence';
  if (linked.some((a) => a.type === 'warning')) return 'warning';
  return 'unchecked';
}

function isAnomalyResolved(a: Anomaly, states: Record<string, FieldState>): boolean {
  if (!a.fieldId) return true;
  const fs = states[a.fieldId];
  if (!fs) return false;
  if (a.type === 'blocking_error') return fs.status === 'modified';
  return fs.status === 'confirmed' || fs.status === 'modified';
}

function buildFieldStates(ticket: ReviewTicket): Record<string, FieldState> {
  const states: Record<string, FieldState> = {};
  for (const f of ticket.fields) {
    const baseline = computeBaseline(f, ticket.anomalies);
    states[f.id] = {
      fieldId: f.id,
      currentValue: f.originalValue,
      baselineStatus: baseline,
      status: baseline,
      changeReason: undefined,
      changedAt: undefined,
    };
  }
  return states;
}

function buildInitialChangeLog(_ticket: ReviewTicket): ChangeRecord[] {
  // 真实数据无预置修改，始终从空变更日志开始。
  return [];
}

function defaultExpandedGroups(ticket: ReviewTicket): Record<string, boolean> {
  const fieldGroup = new Map(ticket.fields.map((f) => [f.id, f.group] as const));
  const anomalyGroupIds = new Set<string>();
  for (const a of ticket.anomalies) {
    if (a.fieldId) {
      const g = fieldGroup.get(a.fieldId);
      if (g) anomalyGroupIds.add(g);
    }
  }
  const expanded: Record<string, boolean> = {};
  for (const f of ticket.fields) {
    if (expanded[f.group] === undefined) expanded[f.group] = anomalyGroupIds.has(f.group);
  }
  return expanded;
}

function matchFilters(item: QueueItem, f: QueueFilters): boolean {
  if (f.status !== 'all' && item.status !== f.status) return false;
  if (f.risk !== 'all' && item.riskLevel !== f.risk) return false;
  if (f.type !== 'all' && item.type !== f.type) return false;
  if (f.source !== 'all' && item.type !== f.source) return false; // 简化：来源用类型维度示意
  if (f.sla === 'warning' && item.slaRemainingMin > 60) return false;
  if (f.sla === 'timeout' && item.slaRemainingMin >= 0) return false;
  if (f.sla === 'normal' && item.slaRemainingMin <= 60) return false;
  if (f.lowConfidence && !item.hasLowConfidence) return false;
  if (f.validationError && !item.hasValidationError) return false;
  if (f.modified && !item.modified) return false;
  if (f.keyword) {
    const kw = f.keyword.toLowerCase();
    if (!item.serialNumber.toLowerCase().includes(kw) && !item.title.toLowerCase().includes(kw))
      return false;
  }
  return true;
}

// ---------------------------------------------------------------------------
// Store 定义
// ---------------------------------------------------------------------------

interface ReviewStore {
  // 队列
  queue: QueueItem[];
  filters: QueueFilters;
  savedViews: SavedView[];
  selectedId: string | null;
  processedCount: number;

  // 当前工单
  ticket: ReviewTicket | null;
  fieldStates: Record<string, FieldState>;
  changeLog: ChangeRecord[];
  auditLogs: ReviewTicket['auditLogs'];
  notes: string;

  // 异步/UI 状态
  queueLoading: boolean;
  ticketLoading: boolean;
  error: string | null;
  sessionId: string;
  autoSaveStatus: AutoSaveStatus;
  conflict: ConflictInfo | null;
  beingEditedBy: string | null;
  dirty: boolean;
  pendingSwitchId: string | null;

  // 决策/提交
  decision: ReviewDecision | null;
  submitDialogOpen: boolean;
  submitting: boolean;
  submittedToast: string | null;
  queueEmpty: boolean;

  // UI
  density: 'standard' | 'compact';
  leftCollapsed: boolean;
  rightCollapsed: boolean;
  fieldFilter: FieldFilter;
  expandedGroups: Record<string, boolean>;
  editingFieldId: string | null;
  locatingFieldId: string | null;
  locatingTick: number;

  // actions
  init: () => Promise<void>;
  setFilters: (patch: Partial<QueueFilters>) => void;
  applySavedView: (view: SavedView) => void;
  selectTicket: (id: string) => void;
  confirmSwitch: () => void;
  cancelSwitch: () => void;
  loadTicketById: (id: string) => Promise<void>;
  prevTicket: () => void;
  nextTicket: () => void;

  setFieldValue: (fieldId: string, value: unknown, reason: string) => void;
  confirmField: (fieldId: string) => void;
  resetField: (fieldId: string) => void;
  undoChange: (fieldId: string) => void;
  useSuggestion: (fieldId: string) => void;
  setFieldRemark: (fieldId: string, remark: string) => void;
  toggleUncertain: (fieldId: string) => void;

  setNotes: (text: string) => void;
  appendNotePhrase: (phrase: string) => void;

  stash: () => void;
  openSubmitDialog: (decision: ReviewDecision) => void;
  closeSubmitDialog: () => void;
  submit: (decision: ReviewDecision, openNext: boolean) => Promise<void>;
  clearSubmittedToast: () => void;

  resolveConflict: (mode: 'merge' | 'discard') => void;
  triggerConflictDemo: () => void;
  triggerBeingEditedDemo: () => void;
  clearBeingEdited: () => void;

  toggleDensity: () => void;
  toggleLeft: () => void;
  toggleRight: () => void;
  setFieldFilter: (filter: FieldFilter) => void;
  toggleGroup: (groupId: string) => void;
  setEditingField: (fieldId: string | null) => void;
  locateField: (fieldId: string) => void;
  jumpToNextAnomaly: () => void;
  setAutoSaveStatus: (s: AutoSaveStatus) => void;
}

const defaultFilters: QueueFilters = {
  status: 'all',
  risk: 'all',
  type: 'all',
  source: 'all',
  sla: 'all',
  lowConfidence: false,
  validationError: false,
  modified: false,
  keyword: '',
};

export const useReviewStore = create<ReviewStore>((set, get) => ({
  queue: [],
  filters: defaultFilters,
  savedViews: DEFAULT_SAVED_VIEWS,
  selectedId: null,
  processedCount: 0,

  ticket: null,
  fieldStates: {},
  changeLog: [],
  auditLogs: [],
  notes: '',

  autoSaveStatus: 'idle',
  queueLoading: false,
  ticketLoading: false,
  error: null,
  sessionId: '',
  conflict: null,
  beingEditedBy: null,
  dirty: false,
  pendingSwitchId: null,

  decision: null,
  submitDialogOpen: false,
  submitting: false,
  submittedToast: null,
  queueEmpty: false,

  density: 'standard',
  leftCollapsed: false,
  rightCollapsed: true,
  fieldFilter: 'all',
  expandedGroups: {},
  editingFieldId: null,
  locatingFieldId: null,
  locatingTick: 0,

  init: async () => {
    set({ queueLoading: true, error: null });
    try {
      // 生成审核会话 ID（幂等性标识）
      const sessionId = crypto.randomUUID
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

      const summaries = await fetchWorkOrderList();
      const queue: QueueItem[] = summaries.map(workOrderSummaryToQueueItem);

      if (queue.length === 0) {
        set({ queue, queueLoading: false, sessionId, queueEmpty: true });
        return;
      }

      const first = queue[0];
      set({ queue, selectedId: first.id, queueLoading: false, sessionId });
      await get().loadTicketById(first.id);
    } catch (e) {
      set({
        queueLoading: false,
        error: `加载队列失败: ${(e as Error).message}`,
      });
    }
  },

  setFilters: (patch) => set((s) => ({ filters: { ...s.filters, ...patch } })),
  applySavedView: (view) =>
    set((s) => ({ filters: { ...defaultFilters, ...view.filters } })),

  selectTicket: (id) => {
    if (id === get().selectedId) return;
    if (get().dirty) {
      set({ pendingSwitchId: id });
      return;
    }
    get().loadTicketById(id);
  },
  confirmSwitch: () => {
    const id = get().pendingSwitchId;
    set({ pendingSwitchId: null, dirty: false });
    if (id) get().loadTicketById(id);
  },
  cancelSwitch: () => set({ pendingSwitchId: null }),

  loadTicketById: async (id) => {
    set({ ticketLoading: true, error: null });
    try {
      const [data, sessions] = await Promise.all([
        fetchWorkOrder(id),
        fetchAuditLogs(id).catch(() => []),
      ]);
      const auditEntries = auditLogSessionsToEntries(sessions);
      const ticket = workOrderDataToReviewTicket(data, auditEntries);

      set({
        selectedId: id,
        ticket,
        fieldStates: buildFieldStates(ticket),
        changeLog: buildInitialChangeLog(ticket),
        auditLogs: ticket.auditLogs,
        notes: '',
        dirty: false,
        expandedGroups: defaultExpandedGroups(ticket),
        fieldFilter: 'all',
        editingFieldId: null,
        locatingFieldId: null,
        autoSaveStatus: 'idle',
        beingEditedBy: null,
        conflict: null,
        ticketLoading: false,
      });
    } catch (e) {
      set({
        ticketLoading: false,
        error: `加载工单失败: ${(e as Error).message}`,
      });
    }
  },

  prevTicket: () => {
    const { queue, filters, selectedId } = get();
    const list = queue.filter((i) => matchFilters(i, filters));
    const idx = list.findIndex((i) => i.id === selectedId);
    const prev = list[idx - 1];
    if (prev) get().selectTicket(prev.id);
  },
  nextTicket: () => {
    const { queue, filters, selectedId } = get();
    const list = queue.filter((i) => matchFilters(i, filters));
    const idx = list.findIndex((i) => i.id === selectedId);
    const next = list[idx + 1];
    if (next) get().selectTicket(next.id);
  },

  setFieldValue: (fieldId, value, reason) => {
    const { ticket, fieldStates } = get();
    if (!ticket) return;
    const field = ticket.fields.find((f) => f.id === fieldId);
    if (!field) return;
    const prev = fieldStates[fieldId];
    const reverted = valuesEqual(value, field.originalValue);
    const nextStatus: FieldReviewStatus = reverted ? prev.baselineStatus : 'modified';
    const ts = nowIso();
    set((s) => ({
      fieldStates: {
        ...s.fieldStates,
        [fieldId]: {
          ...prev,
          currentValue: value,
          status: nextStatus,
          changeReason: reverted ? undefined : reason,
          changedAt: reverted ? undefined : ts,
        },
      },
      changeLog: [
        {
          id: uid('cl'),
          fieldId,
          fieldName: field.name,
          before: prev.currentValue,
          after: value,
          reason,
          timestamp: ts,
          kind: 'supplement',
        },
        ...s.changeLog,
      ],
      auditLogs: [
        {
          id: uid('al'),
          timestamp: ts,
          category: 'field_change',
          actor: '张三',
          action: reverted ? `重置「${field.name}」` : `修改「${field.name}」`,
          detail: undefined,
        },
        ...s.auditLogs,
      ],
      dirty: true,
      autoSaveStatus: 'saving',
      editingFieldId: null,
    }));
  },

  confirmField: (fieldId) => {
    const { ticket, fieldStates } = get();
    if (!ticket) return;
    const field = ticket.fields.find((f) => f.id === fieldId);
    const prev = fieldStates[fieldId];
    if (!prev) return;
    const ts = nowIso();
    set((s) => ({
      fieldStates: { ...s.fieldStates, [fieldId]: { ...prev, status: 'confirmed' } },
      auditLogs: [
        {
          id: uid('al'),
          timestamp: ts,
          category: 'field_change',
          actor: '张三',
          action: `确认「${field?.name ?? fieldId}」`,
        },
        ...s.auditLogs,
      ],
      dirty: true,
      autoSaveStatus: 'saving',
    }));
  },

  resetField: (fieldId) => {
    const { ticket, fieldStates } = get();
    if (!ticket) return;
    const field = ticket.fields.find((f) => f.id === fieldId);
    if (!field) return;
    const prev = fieldStates[fieldId];
    const ts = nowIso();
    set((s) => ({
      fieldStates: {
        ...s.fieldStates,
        [fieldId]: {
          ...prev,
          currentValue: field.originalValue,
          status: prev.baselineStatus,
          changeReason: undefined,
          changedAt: undefined,
          uncertain: false,
        },
      },
      auditLogs: [
        {
          id: uid('al'),
          timestamp: ts,
          category: 'field_change',
          actor: '张三',
          action: `重置「${field.name}」为系统原始值`,
        },
        ...s.auditLogs,
      ],
      dirty: true,
      autoSaveStatus: 'saving',
    }));
  },

  undoChange: (fieldId) => get().resetField(fieldId),

  useSuggestion: (fieldId) => {
    const { ticket } = get();
    if (!ticket) return;
    const field = ticket.fields.find((f) => f.id === fieldId);
    if (!field || field.systemSuggestion === undefined) return;
    get().setFieldValue(fieldId, field.systemSuggestion, 'adopt_suggestion');
  },

  setFieldRemark: (fieldId, remark) =>
    set((s) => ({
      fieldStates: { ...s.fieldStates, [fieldId]: { ...s.fieldStates[fieldId], remark } },
      dirty: true,
    })),

  toggleUncertain: (fieldId) =>
    set((s) => {
      const prev = s.fieldStates[fieldId];
      return {
        fieldStates: { ...s.fieldStates, [fieldId]: { ...prev, uncertain: !prev?.uncertain } },
        dirty: true,
      };
    }),

  setNotes: (text) => set({ notes: text, dirty: true, autoSaveStatus: 'saving' }),
  appendNotePhrase: (phrase) =>
    set((s) => ({
      notes: s.notes ? `${s.notes}\n${phrase}` : phrase,
      dirty: true,
      autoSaveStatus: 'saving',
    })),

  stash: () => {
    set((s) => ({
      autoSaveStatus: 'saved',
      dirty: false,
      submittedToast: '已暂存当前审核进度',
      auditLogs: [
        {
          id: uid('al'),
          timestamp: nowIso(),
          category: 'process',
          actor: '张三',
          action: '暂存审核进度',
        },
        ...s.auditLogs,
      ],
    }));
  },

  openSubmitDialog: (decision) => set({ submitDialogOpen: true, decision }),
  closeSubmitDialog: () => set({ submitDialogOpen: false, submitting: false }),

  submit: async (decision, openNext) => {
    set({ submitting: true, error: null });
    const { ticket, fieldStates, changeLog, queue, filters, selectedId, processedCount, notes, sessionId } = get();
    if (!ticket) return;

    const decisionLabel: Record<ReviewDecision, string> = {
      approved: '审核通过',
      approved_with_changes: '修改后通过',
      returned: '退回补充',
      rejected: '驳回',
      transferred: '转交复核',
      draft: '暂存',
    };

    const ts = nowIso();
    const newAudit = {
      id: uid('al'),
      timestamp: ts,
      category: 'process' as const,
      actor: '客服坐席',
      action: decisionLabel[decision],
      detail: notes ? `备注：${notes}` : undefined,
    };

    // draft / transferred → 本地暂存，不调用 API
    if (decision === 'draft' || decision === 'transferred') {
      set((s) => ({
        auditLogs: [newAudit, ...s.auditLogs],
        submitting: false,
        submitDialogOpen: false,
        dirty: false,
        submittedToast: decisionLabel[decision],
      }));
      return;
    }

    // 调用真实 API 提交
    try {
      const effectiveChanges = computeEffectiveChanges(ticket, fieldStates, changeLog);
      const apiChanges = effectiveChanges.map(changeRecordToFieldChange);
      const isReject = decision === 'returned' || decision === 'rejected';

      await submitReview(ticket.id, {
        session_id: sessionId,
        version: ticket.version,
        changes: apiChanges,
        reject_reason: isReject ? (notes || '无备注') : null,
      });

      // 计算下一条
      const list = queue.filter((i) => matchFilters(i, filters));
      const idx = list.findIndex((i) => i.id === selectedId);
      const nextItem = list[idx + 1] ?? list[idx - 1] ?? null;
      const remainingQueue = queue.filter((i) => i.id !== selectedId);

      set((s) => ({
        auditLogs: [newAudit, ...s.auditLogs],
        submitting: false,
        submitDialogOpen: false,
        processedCount: processedCount + 1,
        dirty: false,
        submittedToast:
          openNext && nextItem
            ? `${decisionLabel[decision]}，已进入下一条工单`
            : decisionLabel[decision],
      }));

      if (openNext && nextItem) {
        setTimeout(() => {
          set({ queue: remainingQueue });
          get().loadTicketById(nextItem.id);
        }, 50);
      } else if (!nextItem) {
        set({ queue: remainingQueue, ticket: null, queueEmpty: true });
      } else {
        set({ queue: remainingQueue });
      }
    } catch (e) {
      if (e instanceof ConflictError) {
        set({
          submitting: false,
          submitDialogOpen: false,
          conflict: {
            otherUser: '其他审核人',
            theirVersion: ticket.version + 1,
            theirChanges: [],
          },
        });
      } else {
        set({
          submitting: false,
          error: `提交失败: ${(e as Error).message}`,
        });
      }
    }
  },

  clearSubmittedToast: () => set({ submittedToast: null }),

  resolveConflict: (mode) => {
    if (mode === 'discard') {
      // 放弃我的修改：重新加载工单（最新版本）
      const id = get().selectedId;
      set({ conflict: null, dirty: false });
      if (id) get().loadTicketById(id);
    } else {
      // 使用最新版本并合并：保留我的当前修改，仅提升版本号、关闭弹窗
      set((s) => ({
        conflict: null,
        ticket: s.ticket ? { ...s.ticket, version: (s.conflict?.theirVersion ?? s.ticket.version) + 1 } : s.ticket,
      }));
    }
  },
  triggerConflictDemo: () => set({ conflict: CONFLICT_DEMO }),
  triggerBeingEditedDemo: () => set({ beingEditedBy: '李四' }),
  clearBeingEdited: () => set({ beingEditedBy: null }),

  toggleDensity: () => set((s) => ({ density: s.density === 'standard' ? 'compact' : 'standard' })),
  toggleLeft: () => set((s) => ({ leftCollapsed: !s.leftCollapsed })),
  toggleRight: () => set((s) => ({ rightCollapsed: !s.rightCollapsed })),
  setFieldFilter: (filter) => set({ fieldFilter: filter }),
  toggleGroup: (groupId) =>
    set((s) => ({ expandedGroups: { ...s.expandedGroups, [groupId]: !s.expandedGroups[groupId] } })),
  setEditingField: (fieldId) => set({ editingFieldId: fieldId }),
  locateField: (fieldId) => set((s) => ({ locatingFieldId: fieldId, locatingTick: s.locatingTick + 1 })),
  jumpToNextAnomaly: () => {
    const { ticket, fieldStates, locatingFieldId } = get();
    if (!ticket) return;
    const order = ticket.fields.map((f) => f.id);
    const unresolved = ticket.anomalies.filter((a) => !isAnomalyResolved(a, fieldStates) && a.fieldId);
    const fieldIds = unresolved.map((a) => a.fieldId!).filter((id) => order.includes(id));
    if (fieldIds.length === 0) return;
    const curIdx = locatingFieldId ? order.indexOf(locatingFieldId) : -1;
    const after = fieldIds.find((id) => order.indexOf(id) > curIdx);
    get().locateField(after ?? fieldIds[0]);
  },
  setAutoSaveStatus: (s) => set({ autoSaveStatus: s }),
}));

// ---------------------------------------------------------------------------
// 选择器（派生数据）+ 便捷 hooks
// ---------------------------------------------------------------------------

export function selectFilteredQueue(state: ReviewStore): QueueItem[] {
  return state.queue.filter((i) => matchFilters(i, state.filters));
}

export function selectEffectiveChanges(state: ReviewStore): EffectiveChange[] {
  return computeEffectiveChanges(state.ticket, state.fieldStates, state.changeLog);
}

/** 纯函数：根据 ticket/fieldStates/changeLog 计算有效变更（字段改回原值自动移除） */
export function computeEffectiveChanges(
  ticket: ReviewTicket | null,
  fieldStates: Record<string, FieldState>,
  changeLog: ChangeRecord[],
): EffectiveChange[] {
  if (!ticket) return [];
  const result: EffectiveChange[] = [];
  for (const f of ticket.fields) {
    const fs = fieldStates[f.id];
    if (!fs) continue;
    if (!valuesEqual(fs.currentValue, f.originalValue)) {
      result.push({
        fieldId: f.id,
        fieldName: f.name,
        before: f.originalValue,
        after: fs.currentValue,
        reason: fs.changeReason ?? 'other',
        changedAt: fs.changedAt ?? nowIso(),
        kind: changeLog.find((c) => c.fieldId === f.id)?.kind ?? 'modify',
        group: f.group,
      });
    }
  }
  return result;
}

export function selectReviewProgress(state: ReviewStore): ReviewProgress {
  if (!state.ticket) return { total: 0, confirmed: 0, modified: 0, pendingAnomalies: 0, unconfirmedKeyFields: 0 };
  const fields = state.ticket.fields;
  const st = state.fieldStates;
  return {
    total: fields.length,
    confirmed: fields.filter((f) => st[f.id]?.status === 'confirmed').length,
    modified: fields.filter((f) => st[f.id]?.status === 'modified').length,
    pendingAnomalies: state.ticket.anomalies.filter((a) => !isAnomalyResolved(a, st)).length,
    unconfirmedKeyFields: fields.filter(
      (f) => f.isKey && st[f.id]?.status !== 'confirmed' && st[f.id]?.status !== 'modified',
    ).length,
  };
}

export function selectCanSubmit(state: ReviewStore): boolean {
  if (!state.ticket) return false;
  return !state.ticket.anomalies.some(
    (a) => a.type === 'blocking_error' && !isAnomalyResolved(a, state.fieldStates),
  );
}

export function selectBlockingFields(state: ReviewStore): { fieldId: string; message: string }[] {
  return computeBlockingFields(state.ticket, state.fieldStates);
}

/** 纯函数：计算未解决的阻断字段 */
export function computeBlockingFields(
  ticket: ReviewTicket | null,
  fieldStates: Record<string, FieldState>,
): { fieldId: string; message: string }[] {
  if (!ticket) return [];
  return ticket.anomalies
    .filter((a) => a.type === 'blocking_error' && !isAnomalyResolved(a, fieldStates))
    .map((a) => ({ fieldId: a.fieldId!, message: a.message }));
}

export function selectUnresolvedAnomalies(state: ReviewStore): Anomaly[] {
  if (!state.ticket) return [];
  return state.ticket.anomalies.filter((a) => !isAnomalyResolved(a, state.fieldStates));
}

export function selectQueueStats(state: ReviewStore) {
  const list = selectFilteredQueue(state);
  return {
    pending: list.filter((i) => i.status === 'pending_review' || i.status === 'reviewing').length,
    nearTimeout: list.filter((i) => i.slaRemainingMin <= 60 && i.slaRemainingMin >= 0).length,
    stashed: list.filter((i) => i.status === 'stashed').length,
    processed: state.processedCount,
  };
}

export const useFilteredQueue = () => useReviewStore(useShallow(selectFilteredQueue));
export const useEffectiveChanges = () => {
  const ticket = useReviewStore((s) => s.ticket);
  const fieldStates = useReviewStore((s) => s.fieldStates);
  const changeLog = useReviewStore((s) => s.changeLog);
  return useMemo(
    () => computeEffectiveChanges(ticket, fieldStates, changeLog),
    [ticket, fieldStates, changeLog],
  );
};
export const useReviewProgress = () => useReviewStore(useShallow(selectReviewProgress));
export const useCanSubmit = () => useReviewStore(selectCanSubmit);
export const useBlockingFields = () => {
  const ticket = useReviewStore((s) => s.ticket);
  const fieldStates = useReviewStore((s) => s.fieldStates);
  return useMemo(() => computeBlockingFields(ticket, fieldStates), [ticket, fieldStates]);
};
export const useUnresolvedAnomalies = () => useReviewStore(useShallow(selectUnresolvedAnomalies));
export const useQueueStats = () => useReviewStore(useShallow(selectQueueStats));
