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
} from '../lib/constants';
import { valuesEqual } from '../lib/format';
import { getCurrentUserName } from '../../auth/parseUser';
import { CONFLICT_DEMO } from '../mock/mockData';
import { QUEUE as MOCK_QUEUE, buildTicket } from '../mock/mockData';
import {
  fetchWorkOrderList,
  fetchNextWorkOrder,
  fetchWorkOrder,
  fetchAuditLogs,
  fetchConfirm,
  stashWorkOrder,
  fetchStashData,
  deleteStashData,
  ConflictError,
  LockLostError,
  ValidationError,
} from '../../api/review';
import {
  workOrderSummaryToQueueItem,
  workOrderDataToReviewTicket,
  auditLogSessionsToEntries,
  changeRecordToFieldChange,
} from '../lib/converters';

let _uid = 0;
const USE_MOCK_DATA = import.meta.env.DEV && import.meta.env.VITE_USE_MOCK_DATA === 'true';
const submitKeys = new Map<string, string>();
function uid(prefix = 'id'): string {
  _uid += 1;
  return `${prefix}-${_uid}`;
}

// ---------------------------------------------------------------------------
// 纯函数：派生计算
// ---------------------------------------------------------------------------

const VALID_FIELD_STATUSES: readonly FieldReviewStatus[] = [
  'unchecked', 'confirmed', 'modified', 'warning', 'blocking_error',
];

function parseFieldReviewStatus(s: unknown): FieldReviewStatus {
  if (typeof s === 'string' && (VALID_FIELD_STATUSES as readonly string[]).includes(s)) {
    return s as FieldReviewStatus;
  }
  return 'unchecked';
}

function computeBaseline(field: FieldDef, anomalies: Anomaly[]): FieldReviewStatus {
  const linked = anomalies.filter((a) => a.fieldId === field.id);
  if (linked.some((a) => a.type === 'blocking_error')) return 'blocking_error';
  if (linked.some((a) => a.type === 'warning')) return 'warning';
  return 'unchecked';
}

function isAnomalyResolved(a: Anomaly, states: Record<string, FieldState>): boolean {
  if (!a.fieldId) return a.type !== 'blocking_error';
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
      currentValue: f.currentValue ?? f.originalValue,
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

export function computeDefaultExpandedGroups(ticket: ReviewTicket): Record<string, boolean> {
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
    if (expanded[f.group] === undefined) {
      expanded[f.group] = anomalyGroupIds.size > 0
        ? anomalyGroupIds.has(f.group)
        : f.group === 'basic';
    }
  }
  return expanded;
}

function matchFilters(item: QueueItem, f: QueueFilters): boolean {
  if (f.status !== 'all' && item.status !== f.status) return false;
  if (f.type !== 'all' && item.type !== f.type) return false;
  if (f.source !== 'all' && item.source !== f.source) return false;
  if (f.sla === 'warning' && item.slaRemainingMin > 60) return false;
  if (f.sla === 'timeout' && item.slaRemainingMin >= 0) return false;
  if (f.sla === 'normal' && item.slaRemainingMin <= 60) return false;
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
  lockState: 'acquiring' | 'locked' | 'lost' | 'error' | 'released';  // F2: 锁丢失强阻塞；released=提交成功后终态，锁已由后端释放
  lockFencingToken: number | null;
  dirty: boolean;
  pendingSwitchId: string | null;
  currentLoadId: number;  // F4: 切单竞态保护

  // 决策/提交
  decision: ReviewDecision | null;
  submitDialogOpen: boolean;
  submitting: boolean;
  submittedToast: string | null;
  /** 操作被拦截时的轻量错误提示（如已确认工单禁止编辑） */
  errorNotice: string | null;
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
  init: (preferredId?: string) => Promise<void>;
  setFilters: (patch: Partial<QueueFilters>) => void;
  applySavedView: (view: SavedView) => void;
  selectTicket: (id: string) => void;
  confirmSwitch: () => Promise<void>;
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

  stash: () => Promise<void>;
  saveDraft: () => Promise<void>;
  discardDraft: () => Promise<void>;
  openSubmitDialog: (decision: ReviewDecision) => void;
  closeSubmitDialog: () => void;
  submit: (decision: ReviewDecision, openNext: boolean) => Promise<void>;
  clearSubmittedToast: () => void;
  setErrorNotice: (msg: string) => void;
  clearErrorNotice: () => void;

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
  setLockState: (s: 'acquiring' | 'locked' | 'lost' | 'error') => void;  // F2
}

const defaultFilters: QueueFilters = {
  // 默认只展示待审核工单，避免用户误入已确认/已暂存等不可编辑工单
  status: 'pending_review',
  type: 'all',
  source: 'all',
  sla: 'all',
  validationError: false,
  modified: false,
  keyword: '',
};

export const useReviewStore = create<ReviewStore>((set, get) => ({
  queue: [],
  filters: defaultFilters,
  savedViews: DEFAULT_SAVED_VIEWS,
  selectedId: null,

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
  lockState: 'acquiring',
  lockFencingToken: null,
  dirty: false,
  pendingSwitchId: null,
  currentLoadId: 0,

  decision: null,
  submitDialogOpen: false,
  submitting: false,
  submittedToast: null,
  errorNotice: null,
  queueEmpty: false,

  density: 'standard',
  leftCollapsed: typeof window === 'undefined' || window.innerWidth < 1024,
  rightCollapsed: typeof window === 'undefined' || window.innerWidth < 1440,
  fieldFilter: 'abnormal',
  expandedGroups: {},
  editingFieldId: null,
  locatingFieldId: null,
  locatingTick: 0,

  init: async (preferredId) => {
    if (get().queueLoading) return;
    set({ queueLoading: true, error: null });
    try {
      // 生成审核会话 ID（幂等性标识）
      const sessionId = crypto.randomUUID
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

      const status = get().filters.status;
      const queue: QueueItem[] = USE_MOCK_DATA
        ? MOCK_QUEUE.filter((item) => status === 'all' || item.status === status)
        : (await fetchWorkOrderList(status === 'all' ? undefined : status)).map(workOrderSummaryToQueueItem);
      const eligible = queue.filter((item) => matchFilters(item, get().filters));
      let first: { id: string } | undefined;
      if (preferredId) {
        first = queue.find((item) => item.id === preferredId) ?? { id: preferredId };
      } else if (!USE_MOCK_DATA && status === 'pending_review' && eligible.length > 0) {
        const nextId = await fetchNextWorkOrder();
        first = nextId ? eligible.find((item) => item.id === nextId) ?? { id: nextId } : undefined;
      } else {
        first = eligible[0];
      }

      if (!first) {
        set((s) => ({
          queue,
          selectedId: null,
          ticket: null,
          fieldStates: {},
          changeLog: [],
          auditLogs: [],
          notes: '',
          queueLoading: false,
          ticketLoading: false,
          sessionId,
          queueEmpty: true,
          dirty: false,
          currentLoadId: s.currentLoadId + 1,
        }));
        return;
      }

      set({ queue, selectedId: first.id, queueLoading: false, sessionId, queueEmpty: false });
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
  confirmSwitch: async () => {
    const id = get().pendingSwitchId;
    const currentTicketId = get().ticket?.id;
    set({ pendingSwitchId: null, dirty: false });
    // 清除自动保存的暂存数据，避免重新打开时恢复"已丢弃"的修改
    if (currentTicketId) {
      const fencingToken = get().lockFencingToken;
      if (fencingToken !== null) deleteStashData(currentTicketId, fencingToken).catch((err) => {
        console.warn('删除暂存数据失败，工单重新打开时可能恢复已丢弃的修改', currentTicketId, err);
      });
    }
    if (id) get().loadTicketById(id);
  },
  cancelSwitch: () => set({ pendingSwitchId: null }),

  loadTicketById: async (id) => {
    // F4: 切单竞态保护 — 记录请求序列号，丢弃过期响应
    const reqId = get().currentLoadId + 1;
    set({ ticketLoading: true, error: null, currentLoadId: reqId });
    try {
      if (USE_MOCK_DATA) {
        const item = MOCK_QUEUE.find((candidate) => candidate.id === id);
        if (!item) throw new Error('模拟工单不存在');
        const ticket = { ...buildTicket(item), anomalies: [] };
        set({
          selectedId: id,
          ticket,
          fieldStates: buildFieldStates(ticket),
          changeLog: [],
          auditLogs: ticket.auditLogs,
          notes: '',
          dirty: false,
          ticketLoading: false,
          autoSaveStatus: 'saved',
        });
        return;
      }
      const [data, sessions, stashData] = await Promise.all([
        fetchWorkOrder(id),
        fetchAuditLogs(id).catch(() => []),
        fetchStashData(id).catch(() => null),
      ]);
      // 丢弃过期响应
      if (reqId !== get().currentLoadId) return;
      const auditEntries = auditLogSessionsToEntries(sessions);
      const ticket = workOrderDataToReviewTicket(data, auditEntries);

      set((state) => state.queue.some((item) => item.id === id) ? state : {
        queue: [...state.queue, {
          id,
          serialNumber: ticket.serialNumber,
          title: ticket.title,
          type: ticket.type,
          source: ticket.source,
          status: ticket.status === 'rejected' || ticket.status === 'approved'
            ? 'confirmed'
            : ticket.status,
          anomalyCount: ticket.anomalies.length,
          slaRemainingMin: ticket.slaRemainingMin,
          createdAt: ticket.createdAt,
          urgency: ticket.urgency,
        }],
      });

      // 构建初始字段状态，然后用暂存数据覆盖
      const baseFieldStates = buildFieldStates(ticket);
      let restoredNotes = '';
      if (stashData && stashData.field_states) {
        restoredNotes = stashData.notes || '';
        for (const [fieldId, stashed] of Object.entries(stashData.field_states)) {
          if (baseFieldStates[fieldId] && stashed && typeof stashed === 'object') {
            baseFieldStates[fieldId] = {
              ...baseFieldStates[fieldId],
              currentValue: 'currentValue' in stashed ? stashed.currentValue : baseFieldStates[fieldId].currentValue,
              status: parseFieldReviewStatus(stashed.status),
              changeReason: typeof stashed.changeReason === 'string' ? stashed.changeReason : baseFieldStates[fieldId].changeReason,
            };
          }
        }
      }

      set({
        selectedId: id,
        ticket,
        fieldStates: baseFieldStates,
        changeLog: buildInitialChangeLog(ticket),
        auditLogs: ticket.auditLogs,
        notes: restoredNotes,
        dirty: false,
        expandedGroups: computeDefaultExpandedGroups(ticket),
        fieldFilter: ticket.anomalies.length > 0 ? 'abnormal' : 'all',
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
    const { ticket, lockState } = get();
    // 已确认/已驳回的工单禁止修改 —— 退出编辑并明确提示，而非静默吞掉点击
    if (ticket && (ticket.status === 'confirmed' || ticket.status === 'rejected')) {
      set({
        editingFieldId: null,
        errorNotice: '该工单已确认/已驳回，字段不可修改',
      });
      return;
    }
    // F2: 锁丢失/错误时禁止编辑 —— 同样给出提示
    if (lockState === 'lost' || lockState === 'error') {
      set({
        editingFieldId: null,
        errorNotice: lockState === 'error' ? '锁服务不可用，无法保存修改' : '编辑锁已丢失，无法保存修改',
      });
      return;
    }
    if (!ticket) return;
    const field = ticket.fields.find((f) => f.id === fieldId);
    if (!field) return;
    const fieldStates = get().fieldStates;
    const prev = fieldStates[fieldId];
    const reverted = valuesEqual(value, field.originalValue);
    const nextStatus: FieldReviewStatus = reverted ? prev.baselineStatus : 'modified';
    const ts = new Date().toISOString();
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
          actor: getCurrentUserName(),
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
    const { ticket, lockState, fieldStates } = get();
    if (!ticket || lockState === 'lost' || lockState === 'error') return;
    if (ticket.status === 'confirmed' || ticket.status === 'rejected') return;
    const field = ticket.fields.find((f) => f.id === fieldId);
    const prev = fieldStates[fieldId];
    if (!field || !prev || prev.status === 'blocking_error') return;
    const ts = new Date().toISOString();
    set((s) => ({
      fieldStates: {
        ...s.fieldStates,
        [fieldId]: { ...prev, status: 'confirmed', changedAt: ts },
      },
      auditLogs: [{
        id: uid('al'),
        timestamp: ts,
        category: 'field_change',
        actor: getCurrentUserName(),
        action: `确认「${field.name}」无误`,
      }, ...s.auditLogs],
      dirty: true,
      autoSaveStatus: 'saving',
    }));
  },

  resetField: (fieldId) => {
    const { ticket, fieldStates } = get();
    if (!ticket) return;
    // 已确认/已驳回的工单禁止继续编辑
    if (ticket.status === 'confirmed' || ticket.status === 'rejected') return;
    const field = ticket.fields.find((f) => f.id === fieldId);
    if (!field) return;
    const prev = fieldStates[fieldId];
    const ts = new Date().toISOString();
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
          actor: getCurrentUserName(),
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
      autoSaveStatus: 'saving',
    })),

  toggleUncertain: (fieldId) =>
    set((s) => {
      const prev = s.fieldStates[fieldId];
      return {
        fieldStates: { ...s.fieldStates, [fieldId]: { ...prev, uncertain: !prev?.uncertain } },
        dirty: true,
        autoSaveStatus: 'saving',
      };
    }),

  setNotes: (text) => set({ notes: text, dirty: true, autoSaveStatus: 'saving' }),
  appendNotePhrase: (phrase) =>
    set((s) => ({
      notes: s.notes ? `${s.notes}\n${phrase}` : phrase,
      dirty: true,
      autoSaveStatus: 'saving',
    })),

  stash: async () => {
    // F2: 锁丢失/错误时禁止暂存
    if (get().lockState === 'lost' || get().lockState === 'error') return;
    const { ticket, fieldStates, notes, queue, filters, selectedId, lockFencingToken } = get();
    if (!ticket || lockFencingToken === null) return;
    // 已确认工单禁止暂存：后端 manual stash 会将 confirmed 回退为 stashed
    if (ticket.status === 'confirmed') {
      set({ error: '该工单已确认，不能暂存' });
      return;
    }

    if (USE_MOCK_DATA) {
      const list = queue.filter((item) => matchFilters(item, filters));
      const index = list.findIndex((item) => item.id === selectedId);
      const nextItem = list[index + 1] ?? null;
      set({
        queue: queue.filter((item) => item.id !== selectedId),
        autoSaveStatus: 'saved',
        dirty: false,
        submittedToast: '已进入稍后处理',
      });
      if (nextItem) await get().loadTicketById(nextItem.id);
      else set({ ticket: null, queueEmpty: true });
      return;
    }

    set({ autoSaveStatus: 'saving' });
    try {
      const payload = Object.fromEntries(
        Object.entries(fieldStates).map(([id, fs]) => [
          id,
          { currentValue: fs.currentValue, status: fs.status, changeReason: fs.changeReason },
        ]),
      );
      await stashWorkOrder(ticket.id, payload, notes, 'manual', lockFencingToken);

      // 计算下一条工单
      const list = queue.filter((i) => matchFilters(i, filters));
      const idx = list.findIndex((i) => i.id === selectedId);
      const nextItem = list[idx + 1] ?? null;
      const remainingQueue = queue.filter((i) => i.id !== selectedId);

      set((s) => ({
        autoSaveStatus: 'saved',
        dirty: false,
        submittedToast: nextItem
          ? '已暂存当前审核进度，进入下一条工单'
          : '已暂存当前审核进度',
        auditLogs: [
          {
            id: uid('al'),
            timestamp: new Date().toISOString(),
            category: 'process',
            actor: getCurrentUserName(),
            action: '暂存审核进度',
          },
          ...s.auditLogs,
        ],
      }));

      // 自动进入下一条（锁已由后端释放）
      if (nextItem) {
        setTimeout(() => {
          set({ queue: remainingQueue });
          get().loadTicketById(nextItem.id);
        }, 50);
      } else {
        set({ queue: remainingQueue, ticket: null, queueEmpty: true });
      }
    } catch (e) {
      if (e instanceof LockLostError) {
        set({ autoSaveStatus: 'failed', lockState: 'lost' });
      } else if (e instanceof ConflictError) {
        set({ autoSaveStatus: 'failed', error: e.message });
      } else {
        set({ autoSaveStatus: 'failed', submittedToast: '暂存失败，请重试' });
      }
    }
  },

  saveDraft: async () => {
    const { ticket, fieldStates, notes, lockFencingToken, lockState } = get();
    if (!ticket || lockFencingToken === null || lockState === 'lost' || lockState === 'error') return;
    if (USE_MOCK_DATA) {
      set({ autoSaveStatus: 'saved', dirty: false, submittedToast: '草稿已暂存' });
      return;
    }
    const payload = Object.fromEntries(
      Object.entries(fieldStates).map(([id, fs]) => [
        id,
        { currentValue: fs.currentValue, status: fs.status, changeReason: fs.changeReason },
      ]),
    );
    set({ autoSaveStatus: 'saving' });
    try {
      await stashWorkOrder(ticket.id, payload, notes, 'auto_save', lockFencingToken);
      set({ autoSaveStatus: 'saved', dirty: false, submittedToast: '草稿已暂存' });
    } catch {
      set({ autoSaveStatus: 'failed', submittedToast: '暂存失败，请重试' });
    }
  },

  discardDraft: async () => {
    const { ticket, lockFencingToken } = get();
    if (!ticket) return;
    if (!USE_MOCK_DATA && lockFencingToken !== null) {
      await deleteStashData(ticket.id, lockFencingToken);
    }
    set({
      fieldStates: buildFieldStates(ticket),
      changeLog: [],
      notes: '',
      dirty: false,
      autoSaveStatus: 'idle',
    });
  },

  openSubmitDialog: (decision) => {
    const { ticket, fieldStates, lockState } = get();
    if (!ticket || ticket.status === 'confirmed' || ticket.status === 'rejected') return;
    if (lockState === 'lost' || lockState === 'error') {
      set({ errorNotice: '编辑锁已丢失，无法提交审核' });
      return;
    }
    const blocking = ticket.anomalies.find(
      (anomaly) => anomaly.type === 'blocking_error' && !isAnomalyResolved(anomaly, fieldStates),
    );
    if (decision !== 'rejected' && blocking) {
      if (blocking.fieldId) get().locateField(blocking.fieldId);
      set({ errorNotice: '仍有阻断问题，处理后才能确认提交' });
      return;
    }
    set({ submitDialogOpen: true, decision });
  },
  closeSubmitDialog: () => set({ submitDialogOpen: false, submitting: false }),

  submit: async (decision, openNext) => {
    // F2: 锁丢失/错误时禁止提交，关闭对话框避免用户困惑
    if (get().lockState === 'lost' || get().lockState === 'error') {
      set({ submitDialogOpen: false, submitting: false, error: '编辑锁已丢失或不可用，请刷新页面后重新审核' });
      return;
    }
    const { ticket, fieldStates, changeLog, queue, filters, selectedId, notes, sessionId, lockFencingToken } = get();
    if (!ticket || lockFencingToken === null) return;
    // 已确认工单禁止重复提交（避免触发后端 409/423）
    if (ticket.status === 'confirmed') {
      console.warn('[submit] 工单已确认，禁止重复提交:', ticket.id);
      set({
        submitting: false,
        submitDialogOpen: false,
        error: '该工单已确认，不能重复提交',
      });
      return;
    }
    set({ submitting: true, error: null });

    if (USE_MOCK_DATA) {
      const list = queue.filter((item) => matchFilters(item, filters));
      const index = list.findIndex((item) => item.id === selectedId);
      const nextItem = list[index + 1] ?? null;
      set({
        queue: queue.filter((item) => item.id !== selectedId),
        submitting: false,
        submitDialogOpen: false,
        dirty: false,
        notes: '',
        submittedToast: decision === 'rejected' ? '已驳回，进入下一条工单' : '审核通过，进入下一条工单',
      });
      if (openNext && nextItem) await get().loadTicketById(nextItem.id);
      else if (!nextItem) set({ ticket: null, queueEmpty: true });
      return;
    }

    const decisionLabel: Record<ReviewDecision, string> = {
      approved: '确认通过',
      approved_with_changes: '修改后确认',
      rejected: '驳回',
      draft: '暂存',
    };

    const ts = new Date().toISOString();
    const newAudit = {
      id: uid('al'),
      timestamp: ts,
      category: 'process' as const,
      actor: getCurrentUserName(),
      action: decisionLabel[decision],
      detail: notes ? `备注：${notes}` : undefined,
    };

    // draft → 调用 stash API 持久化草稿
    if (decision === 'draft') {
      try {
        const payload = Object.fromEntries(
          Object.entries(fieldStates).map(([id, fs]) => [
            id,
            { currentValue: fs.currentValue, status: fs.status, changeReason: fs.changeReason },
          ]),
        );
        await stashWorkOrder(ticket.id, payload, notes, 'manual', lockFencingToken);
        set((s) => ({
          auditLogs: [newAudit, ...s.auditLogs],
          submitting: false,
          submitDialogOpen: false,
          dirty: false,
          submittedToast: decisionLabel[decision],
        }));
      } catch (e) {
        set({
          submitting: false,
          lockState: e instanceof LockLostError ? 'lost' : get().lockState,
          error: e instanceof ConflictError ? e.message
            : e instanceof LockLostError ? null : '暂存失败，请重试',
        });
      }
      return;
    }

    // 调用真实 API 提交
    try {
      const effectiveChanges = computeEffectiveChanges(ticket, fieldStates, changeLog);
      const apiChanges = effectiveChanges.map(changeRecordToFieldChange);
      const isReject = decision === 'rejected';
      const submitKeyId = `${ticket.id}:${sessionId}`;
      let idempotencyKey = submitKeys.get(submitKeyId);
      if (!idempotencyKey) {
        idempotencyKey = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
        submitKeys.set(submitKeyId, idempotencyKey);
      }

      const confirmResp = await fetchConfirm(ticket.id, {
        session_id: sessionId,
        version: ticket.version,
        changes: apiChanges,
        reject_reason: isReject ? notes : null,
        review_notes: notes || null,
        idempotency_key: idempotencyKey,
        lock_fencing_token: lockFencingToken,
      });

      // 计算下一条
      const list = queue.filter((i) => matchFilters(i, filters));
      const idx = list.findIndex((i) => i.id === selectedId);
      const nextItem = list[idx + 1] ?? list[idx - 1] ?? null;
      const remainingQueue = queue.filter((i) => i.id !== selectedId);
      // 提交成功回写工单状态与版本。停留当前工单（未进入下一条）时置
      // lockState='released'：锁已由后端释放，停掉心跳，避免 2 分钟后误报锁丢失。
      const decidedStatus = confirmResp.status === 'rejected' ? 'rejected' : 'confirmed';
      const staying = !(openNext && nextItem);

      set((s) => ({
        auditLogs: [newAudit, ...s.auditLogs],
        submitting: false,
        submitDialogOpen: false,
        dirty: false,
        ticket: s.ticket
          ? {
              ...s.ticket,
              status: decidedStatus,
              version: s.ticket.version + 1,
              syncStatus: confirmResp.sync_status,
            }
          : s.ticket,
        lockState: staying ? 'released' : s.lockState,
        submittedToast:
          openNext && nextItem
            ? `${decisionLabel[decision]}，已进入下一条工单`
            : decisionLabel[decision],
      }));
      submitKeys.delete(submitKeyId);

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
      console.error('[submit] 提交异常:', e instanceof ConflictError ? 'ConflictError' : e instanceof LockLostError ? 'LockLostError' : 'Unknown', e);
      if (e instanceof ConflictError) {
        set({
          submitting: false,
          submitDialogOpen: false,
          conflict: {
            otherUser: '其他审核人',
            theirVersion: e.version ?? ticket.version + 1,
            theirChanges: [],
          },
        });
      } else if (e instanceof LockLostError) {
        // 423：编辑锁已失效 —— 标记锁丢失（StickyDecisionBar 显示 pill 引导刷新），
        // 不设置 error 避免触发全屏错误，保持轻量提示
        set({
          submitting: false,
          submitDialogOpen: false,
          lockState: 'lost',
        });
      } else if (e instanceof ValidationError) {
        const blockingFields = new Set(
          e.issues.filter((issue) => issue.severity === 'blocking' && issue.field).map((issue) => issue.field as string),
        );
        set((s) => ({
          submitting: false,
          submitDialogOpen: false,
          errorNotice: e.message,
          ticket: s.ticket ? {
            ...s.ticket,
            anomalies: e.issues.map((issue, index) => ({
              id: `server-validation-${index}`,
              code: issue.code,
              type: issue.severity === 'blocking' ? 'blocking_error' : issue.severity,
              fieldId: issue.field ?? undefined,
              message: issue.message,
            })),
          } : s.ticket,
          fieldStates: Object.fromEntries(Object.entries(s.fieldStates).map(([id, fs]) => {
            if (blockingFields.has(id)) return [id, { ...fs, status: 'blocking_error' as const }];
            if (fs.status === 'blocking_error' || fs.status === 'warning') {
              const field = s.ticket?.fields.find((item) => item.id === id);
              const changed = field ? !valuesEqual(fs.currentValue, field.originalValue) : false;
              return [id, { ...fs, status: changed ? 'modified' as const : 'unchecked' as const }];
            }
            return [id, fs];
          })),
        }));
      } else {
        console.error('[submit] 提交失败:', e);
        set({
          submitting: false,
          submitDialogOpen: false,
          error: `提交失败: ${(e as Error).message}`,
        });
      }
    }
  },

  clearSubmittedToast: () => set({ submittedToast: null }),
  setErrorNotice: (msg) => set({ errorNotice: msg }),
  clearErrorNotice: () => set({ errorNotice: null }),

  resolveConflict: async (mode) => {
    const id = get().selectedId;
    if (mode === 'discard') {
      // 放弃我的修改：重新加载工单（最新版本）
      set({ conflict: null, dirty: false });
      if (id) get().loadTicketById(id);
    } else {
      // merge：re-fetch 最新版本，覆盖 originalValue，保留我的 currentValue
      set({ ticketLoading: true });
      try {
        const latest = await fetchWorkOrder(id!);
        const latestRec = latest as Record<string, unknown>;
        // 服务端工单已被他人确认/驳回：无法合并，从队列移除并明确提示
        const latestStatus = latestRec.review_status as string | null;
        if (latestStatus === 'confirmed' || latestStatus === 'rejected') {
          set((s) => ({
            conflict: null,
            ticketLoading: false,
            ticket: null,
            queue: s.queue.filter((i) => i.id !== id),
            queueEmpty: s.queue.length <= 1,
            error: `该工单已被他人${latestStatus === 'confirmed' ? '确认' : '驳回'}，无法合并你的修改，工单已从队列移除`,
          }));
          return;
        }
        const latestTicket = workOrderDataToReviewTicket(latest, get().auditLogs);
        const latestFields = new Map(latestTicket.fields.map((f) => [f.id, f.originalValue]));
        set((s) => {
          if (!s.ticket) return { conflict: null, ticketLoading: false };
          const mergedFields = s.ticket.fields.map((f) => ({
            ...f,
            originalValue: latestFields.has(f.id) ? latestFields.get(f.id) : f.originalValue,
          }));
          return {
            conflict: null,
            ticketLoading: false,
            // 以服务端最新 version 为准，避免合并后仍带旧版本号再次 409
            ticket: { ...s.ticket, version: latest.version, fields: mergedFields },
          };
        });
      } catch {
        set({
          ticketLoading: false,
          error: '获取服务端最新版本失败，请检查网络后重试或放弃本地修改',
        });
      }
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
  locateField: (fieldId) => set((s) => {
    const group = s.ticket?.fields.find((field) => field.id === fieldId)?.group;
    const status = s.fieldStates[fieldId]?.status;
    const isAnomaly = s.ticket?.anomalies?.some((anomaly) => anomaly.fieldId === fieldId) ?? false;
    const hiddenByFilter =
      (s.fieldFilter === 'modified' && status !== 'modified') ||
      (s.fieldFilter === 'abnormal' && !isAnomaly && status !== 'blocking_error' && status !== 'warning');
    return {
      fieldFilter: hiddenByFilter ? 'all' : s.fieldFilter,
      expandedGroups: group ? { ...s.expandedGroups, [group]: true } : s.expandedGroups,
      locatingFieldId: fieldId,
      locatingTick: s.locatingTick + 1,
    };
  }),
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
  setLockState: (s) => set({ lockState: s }),
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
        changedAt: fs.changedAt ?? new Date().toISOString(),
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
  // 已确认/已驳回的工单不可再提交
  if (state.ticket.status === 'confirmed' || state.ticket.status === 'rejected') return false;
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
