import { fireEvent, render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { KeyFieldReview } from '../src/workbench/components/workspace/KeyFieldReview';
import { useReviewStore } from '../src/workbench/store/useReviewStore';
import type { ReviewTicket } from '../src/workbench/types';

describe('complete workorder fields', () => {
  it('keeps secondary fields collapsed by default and makes editable fields editable', () => {
    useReviewStore.setState({
      ticket: {
        id: 'wo-1', status: 'pending_review', anomalies: [],
        fields: [
          { id: 'caseAccountId', name: '场站编号', group: 'project', type: 'text', originalValue: 'A-1' },
          { id: 'remark__c', name: '备注', group: 'description', type: 'textarea', originalValue: '原备注' },
          { id: 'ticket_id', name: '工单 ID', group: 'system', type: 'text', originalValue: '1', readonly: true },
        ],
      } as ReviewTicket,
      fieldStates: {
        caseAccountId: { fieldId: 'caseAccountId', currentValue: 'A-1', baselineStatus: 'unchecked', status: 'unchecked' },
        remark__c: { fieldId: 'remark__c', currentValue: '原备注', baselineStatus: 'unchecked', status: 'unchecked' },
        ticket_id: { fieldId: 'ticket_id', currentValue: '1', baselineStatus: 'unchecked', status: 'unchecked' },
      },
    });

    const view = render(<KeyFieldReview />);
    expect(view.queryByText('原备注')).toBeNull();
    fireEvent.click(view.getByRole('button', { name: /查看其他 2 个字段/ }));
    expect(view.getByText('原备注')).not.toBeNull();
    expect(view.queryByRole('button', { name: '编辑工单 ID' })).toBeNull();
    expect(view.queryByRole('button', { name: '修改备注' })).toBeNull();

    fireEvent.doubleClick(view.getByRole('button', { name: '编辑备注' }));
    expect(view.getByDisplayValue('原备注')).not.toBeNull();
  });
});
