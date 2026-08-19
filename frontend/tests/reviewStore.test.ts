import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchNextWorkOrder, fetchWorkOrder, fetchWorkOrderList } from '../src/api/review';
import { computeDefaultExpandedGroups, useReviewStore } from '../src/workbench/store/useReviewStore';
import type { ReviewTicket } from '../src/workbench/types';

vi.mock('../src/api/review', async (importOriginal) => ({
  ...await importOriginal<typeof import('../src/api/review')>(),
  fetchWorkOrderList: vi.fn(),
  fetchNextWorkOrder: vi.fn(),
  fetchWorkOrder: vi.fn(),
}));

const staleTicket = {
  id: 'confirmed-1',
  status: 'confirmed',
  fields: [],
  anomalies: [],
  auditLogs: [],
} as unknown as ReviewTicket;

describe('review queue initialization', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useReviewStore.setState({
      queue: [],
      selectedId: 'confirmed-1',
      ticket: staleTicket,
      fieldStates: { stale: {} as never },
      auditLogs: staleTicket.auditLogs,
      notes: 'stale',
      queueEmpty: false,
      queueLoading: false,
    });
  });

  it.each([
    ['the API is empty', []],
    ['the API only returns a filtered-out confirmed ticket', [{
      id: 'confirmed-1',
      ticket_id: 88,
      review_status: 'confirmed',
      created_at: null,
    }]],
  ])('clears stale workbench data when %s', async (_case, summaries) => {
    vi.mocked(fetchWorkOrderList).mockResolvedValue(summaries);

    await useReviewStore.getState().init();

    expect(fetchWorkOrderList).toHaveBeenCalledWith('pending_review');
    expect(fetchWorkOrder).not.toHaveBeenCalled();
    expect(useReviewStore.getState()).toMatchObject({
      selectedId: null,
      ticket: null,
      fieldStates: {},
      auditLogs: [],
      notes: '',
      queueEmpty: true,
    });
  });

  it('coalesces concurrent initialization into one server-side take', async () => {
    vi.mocked(fetchWorkOrderList).mockResolvedValue([{
      id: 'WO001', ticket_id: 1, review_status: 'pending_review', created_at: null,
    }]);
    vi.mocked(fetchNextWorkOrder).mockResolvedValue(null);

    await Promise.all([useReviewStore.getState().init(), useReviewStore.getState().init()]);

    expect(fetchWorkOrderList).toHaveBeenCalledTimes(1);
    expect(fetchNextWorkOrder).toHaveBeenCalledTimes(1);
  });
});

describe('review group disclosure', () => {
  it('opens only groups containing anomalies', () => {
    const ticket = {
      fields: [
        { id: 'name', group: 'basic' },
        { id: 'province', group: 'project' },
        { id: 'remark', group: 'description' },
      ],
      anomalies: [{ id: 'a1', fieldId: 'province' }],
    } as unknown as ReviewTicket;

    expect(computeDefaultExpandedGroups(ticket)).toEqual({
      basic: false,
      project: true,
      description: false,
    });
  });

  it('opens basic information when no anomaly needs attention', () => {
    const ticket = {
      fields: [
        { id: 'name', group: 'basic' },
        { id: 'province', group: 'project' },
      ],
      anomalies: [],
    } as unknown as ReviewTicket;

    expect(computeDefaultExpandedGroups(ticket)).toEqual({ basic: true, project: false });
  });

  it('reveals a hidden field before locating it', () => {
    useReviewStore.setState({
      ticket: {
        fields: [{ id: 'province', group: 'project' }],
      } as unknown as ReviewTicket,
      fieldFilter: 'abnormal',
      expandedGroups: { project: false },
    });

    useReviewStore.getState().locateField('province');

    expect(useReviewStore.getState()).toMatchObject({
      fieldFilter: 'all',
      expandedGroups: { project: true },
      locatingFieldId: 'province',
    });
  });

  it('can confirm a non-blocking anomaly without changing its value', () => {
    useReviewStore.setState({
      ticket: {
        status: 'pending_review',
        fields: [{ id: 'province', name: '项目省份', group: 'project' }],
      } as unknown as ReviewTicket,
      fieldStates: {
        province: {
          fieldId: 'province',
          currentValue: '广东',
          baselineStatus: 'warning',
          status: 'warning',
        },
      },
      lockState: 'locked',
      auditLogs: [],
    });

    useReviewStore.getState().confirmField('province');

    expect(useReviewStore.getState().fieldStates.province.status).toBe('confirmed');
    expect(useReviewStore.getState().dirty).toBe(true);
  });
});
