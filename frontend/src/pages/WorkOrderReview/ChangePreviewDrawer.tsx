// frontend/src/pages/WorkOrderReview/ChangePreviewDrawer.tsx
import React from 'react';
import { Drawer, List, Tag, Button, Space, Empty } from 'antd';
import { ArrowRightOutlined } from '@ant-design/icons';
import type { FieldChange } from './types';

interface Props {
  open: boolean;
  changes: FieldChange[];
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}

export const ChangePreviewDrawer: React.FC<Props> = ({
  open, changes, onConfirm, onCancel, loading,
}) => (
  <Drawer
    title={`变更预览 (${changes.length} 个字段已修改)`}
    open={open}
    onClose={onCancel}
    footer={
      <Space style={{ float: 'right' }}>
        <Button onClick={onCancel}>取消</Button>
        <Button type="primary" onClick={onConfirm} loading={loading}>
          确认提交
        </Button>
      </Space>
    }
  >
    {changes.length === 0 ? (
      <Empty description="未修改任何字段，确认提交" />
    ) : (
      <List
        dataSource={changes}
        renderItem={(item: FieldChange) => (
          <List.Item>
            <div style={{ width: '100%' }}>
              <div style={{ fontWeight: 500, marginBottom: 8 }}>{item.field_label}</div>
              <Space>
                <Tag color="default">AI: {String(item.old_value ?? '-')}</Tag>
                <ArrowRightOutlined />
                <Tag color="orange">修正: {String(item.new_value ?? '-')}</Tag>
              </Space>
              {item.ai_confidence != null && (
                <div style={{ marginTop: 4, color: '#888', fontSize: 12 }}>
                  AI 置信度: {(item.ai_confidence * 100).toFixed(0)}%
                </div>
              )}
            </div>
          </List.Item>
        )}
      />
    )}
  </Drawer>
);
