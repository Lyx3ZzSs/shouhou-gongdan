export interface FieldChange {
  op: 'replace' | 'add' | 'remove';
  path: string;
  field_label: string;
  old_value: unknown;
  new_value: unknown;
  ai_confidence?: number | null;
}

export interface ReviewRequest {
  session_id: string;
  version: number;
  changes: FieldChange[];
  reject_reason: string | null;
}

export interface ReviewResponse {
  review_id: string;
  workorder_id: string;
  status: 'confirmed' | 'rejected';
  change_count: number;
  bad_case_count: number;
  next_status: string;
}

export interface WorkOrderData {
  id: string;
  version: number;
  status: string;
  reject_count: number;
  last_reject_reason: string | null;
  last_rejected_by: string | null;
  last_rejected_at: string | null;
  review_notes: string | null;
  ai_confidence?: number | null;
  // 核心字段
  station_name: string;
  dispatch_name: string;
  project_code: string;
  project_name: string;
  project_province: string;
  customer_name: string;
  problem_description: string;
  feedback_channel: string;
  product_line: string;
  product_category: string;
  product_type: string;
  customer_level: string;
  problem_category_l1: string;
  problem_category_l2: string;
  problem_category_l3: string;
  order_type: string;
  problem_type: string;
  fault_category: string;
  fault_detail: string;
  responsible_person: string;
  responsible_department: string;
  primary_department: string;
  after_sales_person: string;
  transferred_person: string;
  transferred_department: string;
  order_level: string;
  fault_level: string;
  onsite_level: string;
  required_solve_time: string;
  // 只读字段
  serial_number: string;
  created_at: string;
  initiator: string;
  initiator_department: string;
  [key: string]: unknown;
}

export interface LockStatus {
  locked: boolean;
  owner?: string;
  locked_minutes?: number;
}

export interface AuditLogSession {
  session_id: string;
  operator_name: string;
  operated_at: string;
  changes: FieldChange[];
}

export const EXCEPTION_RULES = {
  missing_province: { field: 'project_province', message: '场站省份未填写' },
  missing_category: { field: 'problem_category_l1', message: '问题分类未选择' },
  missing_assignee: { field: 'responsible_person', message: '问题责任人未分配' },
} as const;
