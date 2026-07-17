// frontend/src/pages/WorkOrderReview/WorkOrderHeader.tsx
import React from 'react';
import { Descriptions, Tag, Space } from 'antd';
import type { WorkOrderData } from './types';

interface Props {
  workorder: WorkOrderData;
}

export const WorkOrderHeader: React.FC<Props> = ({ workorder }) => (
  <div style={{ marginBottom: 16 }}>
    <Space style={{ marginBottom: 8 }}>
      <Tag color="blue">待审查</Tag>
      {workorder.ai_confidence != null && workorder.ai_confidence < 0.8 && (
        <Tag color="red">AI 低置信度</Tag>
      )}
    </Space>
    <Descriptions size="small" column={4}>
      <Descriptions.Item label="流水号">{workorder.serial_number}</Descriptions.Item>
      <Descriptions.Item label="发起时间">{workorder.created_at}</Descriptions.Item>
      <Descriptions.Item label="发起人">{workorder.initiator}</Descriptions.Item>
      <Descriptions.Item label="发起部门">{workorder.initiator_department}</Descriptions.Item>
      <Descriptions.Item label="AI 置信度">
        {workorder.ai_confidence != null
          ? `${(workorder.ai_confidence * 100).toFixed(0)}%`
          : '-'}
      </Descriptions.Item>
      <Descriptions.Item label="受理单状态">{workorder.status}</Descriptions.Item>
    </Descriptions>
    {workorder.reject_count > 0 && (
      <div style={{ background: '#fff7e6', padding: '8px 12px', borderRadius: 4, marginTop: 8 }}>
        此工单已被退回 {workorder.reject_count} 次，上次退回原因：
        {workorder.last_reject_reason}（{workorder.last_rejected_by}，{workorder.last_rejected_at}）
      </div>
    )}
  </div>
);
