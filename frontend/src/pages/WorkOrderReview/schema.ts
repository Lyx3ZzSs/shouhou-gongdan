// frontend/src/pages/WorkOrderReview/schema.ts
import type { ISchema } from '@formily/react';

export const reviewSchema: ISchema = {
  type: 'object',
  properties: {
    tabGroup: {
      type: 'void',
      'x-component': 'FormTab',
      properties: {
        basicInfo: {
          type: 'object',
          'x-component': 'FormTab.TabPane',
          'x-component-props': { tab: '基本信息' },
          properties: {
            station_name: {
              type: 'string', title: '场站名称', required: true,
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            dispatch_name: {
              type: 'string', title: '调度名称',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            project_code: {
              type: 'string', title: '项目编号',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            project_name: {
              type: 'string', title: '项目名称',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            project_province: {
              type: 'string', title: '项目省份', required: true,
              'x-decorator': 'FormItem', 'x-component': 'Select',
              'x-reactions': ['{{useAsyncProvinceList()}}'],
            },
            customer_name: {
              type: 'string', title: '大客户简称',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            problem_description: {
              type: 'string', title: '问题描述', required: true,
              'x-decorator': 'FormItem',
              'x-component': 'Input.TextArea',
              'x-component-props': { rows: 3 },
            },
            feedback_channel: {
              type: 'string', title: '反馈渠道',
              'x-decorator': 'FormItem', 'x-component': 'Select',
              enum: [
                { label: '400电话', value: '400' },
                { label: '企业微信', value: 'wechat' },
                { label: '邮件', value: 'email' },
                { label: '小程序', value: 'miniapp' },
              ],
            },
            product_line: {
              type: 'string', title: '产品线',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            product_category: {
              type: 'string', title: '产品类别',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            customer_level: {
              type: 'string', title: '客户级别',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
          },
        },
        classification: {
          type: 'object',
          'x-component': 'FormTab.TabPane',
          'x-component-props': { tab: '分类归属' },
          properties: {
            problem_category_l1: {
              type: 'string', title: '问题分类（一级）', required: true,
              'x-decorator': 'FormItem', 'x-component': 'Select',
              enum: [
                { label: '产品问题', value: 'product' },
                { label: '数据问题', value: 'data' },
                { label: '工程问题', value: 'engineering' },
                { label: '采购问题', value: 'procurement' },
                { label: '其他问题', value: 'other' },
              ],
              'x-reactions': [
                {
                  target: 'tabGroup.classification.problem_category_l2',
                  effects: ['onFieldValueChange'],
                  fulfill: { state: { dataSource: '{{useAsyncCategoryL2($self.value)}}' } },
                },
              ],
            },
            problem_category_l2: {
              type: 'string', title: '问题分类（二级）',
              'x-decorator': 'FormItem', 'x-component': 'Select',
              'x-reactions': [
                {
                  target: 'tabGroup.classification.problem_category_l3',
                  effects: ['onFieldValueChange'],
                  fulfill: { state: { dataSource: '{{useAsyncCategoryL3($self.value)}}' } },
                },
              ],
            },
            problem_category_l3: {
              type: 'string', title: '问题分类（三级）',
              'x-decorator': 'FormItem', 'x-component': 'Select',
            },
            order_type: {
              type: 'string', title: '受理单类型',
              'x-decorator': 'FormItem', 'x-component': 'Select',
              enum: [
                { label: '售后单', value: 'normal' },
                { label: 'A类售后单', value: 'a_class' },
                { label: '大客户售后单', value: 'vip' },
              ],
            },
            problem_type: {
              type: 'string', title: '问题类型',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            fault_category: {
              type: 'string', title: '故障分类',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            fault_detail: {
              type: 'string', title: '故障明细',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
          },
        },
        routing: {
          type: 'object',
          'x-component': 'FormTab.TabPane',
          'x-component-props': { tab: '路由分配' },
          properties: {
            responsible_person: {
              type: 'string', title: '问题责任人', required: true,
              'x-decorator': 'FormItem', 'x-component': 'Select',
              'x-reactions': ['{{useAsyncAssignablePerson()}}'],
            },
            responsible_department: {
              type: 'string', title: '责任部门', required: true,
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            primary_department: {
              type: 'string', title: '一级部门',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            after_sales_person: {
              type: 'string', title: '售后责任人',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            transferred_person: {
              type: 'string', title: '移交后责任人',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            transferred_department: {
              type: 'string', title: '移交后部门',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
          },
        },
        priority: {
          type: 'object',
          'x-component': 'FormTab.TabPane',
          'x-component-props': { tab: '时效等级' },
          properties: {
            order_level: {
              type: 'string', title: '受理单级别', required: true,
              'x-decorator': 'FormItem', 'x-component': 'Radio.Group',
              enum: [
                { label: 'P1 紧急', value: 'P1' },
                { label: 'P2 高', value: 'P2' },
                { label: 'P3 中', value: 'P3' },
                { label: 'P4 低', value: 'P4' },
              ],
            },
            fault_level: {
              type: 'string', title: '故障等级',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            onsite_level: {
              type: 'string', title: '进场等级',
              'x-decorator': 'FormItem', 'x-component': 'Input',
            },
            required_solve_time: {
              type: 'string', title: '要求解决时间',
              'x-decorator': 'FormItem', 'x-component': 'DatePicker',
            },
          },
        },
      },
    },
  },
};
