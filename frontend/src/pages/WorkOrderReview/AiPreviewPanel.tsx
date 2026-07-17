// frontend/src/pages/WorkOrderReview/AiPreviewPanel.tsx
import React from 'react';
import { Card, Descriptions, Tag } from 'antd';
import type { WorkOrderData } from './types';

interface Props {
  workorder: WorkOrderData;
}

const FIELD_GROUPS = [
  {
    title: '基本信息',
    fields: [
      ['station_name', '场站名称'],
      ['dispatch_name', '调度名称'],
      ['project_code', '项目编号'],
      ['project_name', '项目名称'],
      ['project_province', '项目省份'],
      ['customer_name', '大客户简称'],
      ['problem_description', '问题描述'],
      ['feedback_channel', '反馈渠道'],
    ],
  },
  {
    title: '分类归属',
    fields: [
      ['problem_category_l1', '一级分类'],
      ['problem_category_l2', '二级分类'],
      ['problem_category_l3', '三级分类'],
      ['order_type', '受理单类型'],
      ['problem_type', '问题类型'],
    ],
  },
  {
    title: '路由分配',
    fields: [
      ['responsible_person', '问题责任人'],
      ['responsible_department', '责任部门'],
      ['primary_department', '一级部门'],
      ['after_sales_person', '售后责任人'],
    ],
  },
  {
    title: '时效等级',
    fields: [
      ['order_level', '受理单级别'],
      ['fault_level', '故障等级'],
      ['required_solve_time', '要求解决时间'],
    ],
  },
];

export const AiPreviewPanel: React.FC<Props> = ({ workorder }) => (
  <div>
    {FIELD_GROUPS.map(group => (
      <Card key={group.title} title={group.title} size="small" style={{ marginBottom: 12 }}>
        <Descriptions size="small" column={1}>
          {group.fields.map(([key, label]) => {
            const value = (workorder as any)[key];
            const confKey = `ai_confidence_${key}`;
            const confidence = (workorder as any)[confKey];
            return (
              <Descriptions.Item key={key} label={label}>
                <Tag color="default">AI: {value ?? '-'}</Tag>
                {confidence != null && confidence < 0.8 && (
                  <Tag color="red">{(confidence * 100).toFixed(0)}%</Tag>
                )}
              </Descriptions.Item>
            );
          })}
        </Descriptions>
      </Card>
    ))}
  </div>
);
