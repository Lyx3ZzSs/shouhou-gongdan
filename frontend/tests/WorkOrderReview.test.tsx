import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { WorkOrderReviewPage } from '../src/pages/WorkOrderReview';
import { fetchWorkOrder, acquireLock } from '../src/api/review';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../src/api/review');

vi.mock('../src/pages/WorkOrderReview/EditFormPanel', () => ({
  EditFormPanel: function EditFormPanel() {
    return null;
  },
}));

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const mockWorkorder = {
  id: 'WO001',
  version: 1,
  status: 'pending_review',
  reject_count: 0,
  last_reject_reason: null,
  last_rejected_by: null,
  last_rejected_at: null,
  ai_confidence: 0.85,
  serial_number: 'SN20260716001',
  created_at: '2026-07-16T10:00:00Z',
  initiator: '客户A',
  initiator_department: '工程部',
  station_name: '测试场站',
  project_province: '广东',
  problem_description: '功率预测偏差大',
  problem_category_l1: 'data',
  order_level: 'P3',
  responsible_person: '李燕昆',
  responsible_department: '数据中心',
  primary_department: '数据中心',
  after_sales_person: '李燕昆',
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('WorkOrderReviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchWorkOrder).mockResolvedValue(mockWorkorder);
    vi.mocked(acquireLock).mockResolvedValue({ locked: true, owner: '张三' });
  });

  it('shows exception alert when province is missing', async () => {
    const woNoProvince = { ...mockWorkorder, project_province: '' };
    vi.mocked(fetchWorkOrder).mockResolvedValue(woNoProvince);

    render(<WorkOrderReviewPage workorderId="WO001" onNavigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText(/场站省份未填写/)).toBeInTheDocument();
    });
  });

  it('submit button is disabled when exceptions exist', async () => {
    const woNoCategory = { ...mockWorkorder, problem_category_l1: '' };
    vi.mocked(fetchWorkOrder).mockResolvedValue(woNoCategory);

    render(<WorkOrderReviewPage workorderId="WO001" onNavigate={vi.fn()} />);

    await waitFor(() => {
      const submitBtns = screen.getAllByRole('button', { name: /确认提交/ });
      // The main-page button (first in DOM order) should be disabled
      expect(submitBtns[0]).toBeDisabled();
    });
  });

  it('shows locked banner when another user holds the lock', async () => {
    vi.mocked(acquireLock).mockResolvedValue({
      locked: false,
      owner: '李四',
      locked_minutes: 3,
    });

    render(<WorkOrderReviewPage workorderId="WO001" onNavigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText(/工单正由 李四 审查中/)).toBeInTheDocument();
    });
  });

  it('shows reject history banner when workorder was rejected before', async () => {
    const woRejected = {
      ...mockWorkorder,
      reject_count: 2,
      last_reject_reason: '分类不准确',
      last_rejected_by: '主管',
      last_rejected_at: '2026-07-16T09:00:00Z',
    };
    vi.mocked(fetchWorkOrder).mockResolvedValue(woRejected);

    render(<WorkOrderReviewPage workorderId="WO001" onNavigate={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText(/此工单已被退回 2 次/)).toBeInTheDocument();
    });
  });
});
