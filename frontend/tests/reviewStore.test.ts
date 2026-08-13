import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchWorkOrder, fetchWorkOrderList } from '../src/api/review';
import { useReviewStore } from '../src/workbench/store/useReviewStore';
import type { ReviewTicket } from '../src/workbench/types';

vi.mock('../src/api/review', async (importOriginal) => ({
  ...await importOriginal<typeof import('../src/api/review')>(),
  fetchWorkOrderList: vi.fn(),
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
    });
  });

  it.each([
    ['the API is empty', []],
    ['the API only returns a filtered-out confirmed ticket', [{
      id: 'confirmed-1',
      ticket_no: '88',
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
});
