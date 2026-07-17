// frontend/src/pages/WorkOrderReview/ExceptionAlert.tsx
import React from 'react';
import { Alert } from 'antd';
import { EXCEPTION_RULES } from './types';

interface Props {
  exceptions: string[];
}

export const ExceptionAlert: React.FC<Props> = ({ exceptions }) => {
  if (exceptions.length === 0) return null;

  const messages = exceptions.map(key => {
    const rule = EXCEPTION_RULES[key as keyof typeof EXCEPTION_RULES];
    return rule ? rule.message : key;
  });

  return (
    <Alert
      type="warning"
      showIcon
      message="异常提醒：以下信息需要修正后才能提交"
      description={
        <ul style={{ margin: 0, paddingLeft: 20 }}>
          {messages.map((msg, i) => <li key={i}>{msg}</li>)}
        </ul>
      }
      style={{ marginBottom: 16 }}
    />
  );
};
