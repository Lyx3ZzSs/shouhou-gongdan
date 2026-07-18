// frontend/src/pages/WorkOrderReview/EditFormPanel.tsx
import React from 'react';
import { createForm } from '@formily/core';
import { createSchemaField } from '@formily/react';
import { Form, FormItem, Input, Select, DatePicker, Radio, FormTab } from '@formily/antd-v5';
import type { Form as FormilyForm } from '@formily/core';
import { reviewSchema } from './schema';
import type { WorkOrderData } from './types';

// ---------------------------------------------------------------------------
// Formily scope — async data providers for x-reactions in the schema.
// TODO: replace with real API calls.
// ---------------------------------------------------------------------------

const PROVINCE_LIST = [
  { label: '北京', value: '北京' },
  { label: '上海', value: '上海' },
  { label: '广东', value: '广东' },
  { label: '浙江', value: '浙江' },
  { label: '江苏', value: '江苏' },
  { label: '四川', value: '四川' },
  { label: '湖北', value: '湖北' },
];

const CATEGORY_L2_MAP: Record<string, { label: string; value: string }[]> = {
  product: [
    { label: '硬件故障', value: 'hardware' },
    { label: '软件缺陷', value: 'software' },
    { label: '固件问题', value: 'firmware' },
  ],
  data: [
    { label: '数据丢失', value: 'data_loss' },
    { label: '数据错误', value: 'data_error' },
  ],
  engineering: [
    { label: '安装问题', value: 'install' },
    { label: '调试问题', value: 'debug' },
  ],
  procurement: [
    { label: '供货延迟', value: 'delay' },
    { label: '型号错误', value: 'wrong_model' },
  ],
  other: [{ label: '其他', value: 'other' }],
};

const CATEGORY_L3_MAP: Record<string, { label: string; value: string }[]> = {
  hardware: [
    { label: '电源模块', value: 'power' },
    { label: '主板故障', value: 'mainboard' },
  ],
  software: [
    { label: '崩溃', value: 'crash' },
    { label: '响应缓慢', value: 'slow' },
  ],
  firmware: [{ label: '版本不兼容', value: 'incompatible' }],
  data_loss: [{ label: '误删除', value: 'accidental_delete' }],
  data_error: [{ label: '格式错误', value: 'format_error' }],
  install: [{ label: '接线错误', value: 'wiring' }],
  debug: [{ label: '参数未配置', value: 'unconfigured' }],
  delay: [{ label: '物流问题', value: 'logistics' }],
  wrong_model: [{ label: '下单错误', value: 'order_error' }],
  other: [{ label: '待确认', value: 'tbd' }],
};

const PERSON_LIST = [
  { label: '李四', value: '李四' },
  { label: '赵六', value: '赵六' },
  { label: '陈七', value: '陈七' },
];

const scope = {
  useAsyncProvinceList() {
    return PROVINCE_LIST;
  },
  useAsyncCategoryL2(parentValue: string) {
    return CATEGORY_L2_MAP[parentValue] ?? [];
  },
  useAsyncCategoryL3(parentValue: string) {
    return CATEGORY_L3_MAP[parentValue] ?? [];
  },
  useAsyncAssignablePerson() {
    return PERSON_LIST;
  },
};

// ---------------------------------------------------------------------------
// Schema field registry
// ---------------------------------------------------------------------------

const SchemaField = createSchemaField({
  components: { FormItem, Input, Select, DatePicker, Radio, FormTab },
  scope,
});

interface Props {
  workorder: WorkOrderData;
  onFormReady: (form: FormilyForm) => void;
}

export const EditFormPanel: React.FC<Props> = ({ workorder, onFormReady }) => {
  const form = React.useMemo(() => createForm({
    initialValues: workorder,
    values: workorder,
  }), [workorder.id, workorder.version]);

  React.useEffect(() => {
    onFormReady(form);
  }, [form, onFormReady]);

  return (
    <Form form={form} layout="vertical">
      <SchemaField schema={reviewSchema} />
    </Form>
  );
};
