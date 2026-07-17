// frontend/src/pages/WorkOrderReview/EditFormPanel.tsx
import React from 'react';
import { createForm } from '@formily/core';
import { createSchemaField } from '@formily/react';
import { Form, FormItem, Input, Select, DatePicker, Radio, FormTab } from '@formily/antd';
import { reviewSchema } from './schema';
import type { WorkOrderData } from './types';

const SchemaField = createSchemaField({
  components: { FormItem, Input, Select, DatePicker, Radio, FormTab },
});

interface Props {
  workorder: WorkOrderData;
  onFormReady: (form: ReturnType<typeof createForm>) => void;
}

export const EditFormPanel: React.FC<Props> = ({ workorder, onFormReady }) => {
  const form = React.useMemo(() => createForm({
    initialValues: workorder,
    values: workorder,
  }), [workorder]);

  React.useEffect(() => {
    onFormReady(form);
  }, [form, onFormReady]);

  return (
    <Form form={form} layout="vertical">
      <SchemaField schema={reviewSchema} />
    </Form>
  );
};
