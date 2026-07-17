import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Row, Col, Button, Space, message, Spin } from 'antd';
import { onFieldValueChange, onFormSubmit } from '@formily/core';
import type { Form } from '@formily/core';
import isEqual from 'lodash.isequal';
import { WorkOrderHeader } from './WorkOrderHeader';
import { AiPreviewPanel } from './AiPreviewPanel';
import { EditFormPanel } from './EditFormPanel';
import { ChangePreviewDrawer } from './ChangePreviewDrawer';
import { ExceptionAlert } from './ExceptionAlert';
import { useReviewLock } from './useReviewLock';
import { fetchWorkOrder, submitReview, ConflictError } from '../../api/review';
import type { WorkOrderData, FieldChange } from './types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createSessionId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // Fallback UUID v4
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface WorkOrderReviewPageProps {
  /** The workorder ID to load and review */
  workorderId: string;
  /** Called after a successful submit or reject to navigate away */
  onNavigate?: (path: string) => void;
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export const WorkOrderReviewPage: React.FC<WorkOrderReviewPageProps> = ({
  workorderId,
  onNavigate,
}) => {
  // ---- state -----------------------------------------------------------
  const [workorder, setWorkorder] = useState<WorkOrderData | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [changes, setChanges] = useState<FieldChange[]>([]);
  const [exceptions, setExceptions] = useState<string[]>([]);
  const [form, setForm] = useState<Form | null>(null);
  const [lockedByOther, setLockedByOther] = useState(false);
  const [lockOwner, setLockOwner] = useState('');
  const [error, setError] = useState<string | null>(null);

  // ---- refs ------------------------------------------------------------
  const sessionIdRef = useRef(createSessionId());
  const changesRef = useRef<FieldChange[]>([]);
  const { tryAcquire, tryRelease } = useReviewLock(workorderId);

  // ---- exception checking ----------------------------------------------
  const checkExceptions = useCallback((data: WorkOrderData) => {
    const result: string[] = [];
    if (!data.project_province) result.push('missing_province');
    if (!data.problem_category_l1) result.push('missing_category');
    if (!data.responsible_person) result.push('missing_assignee');
    setExceptions(result);
    return result;
  }, []);

  // ---- load workorder + acquire lock -----------------------------------
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const wo = await fetchWorkOrder(workorderId);
        if (cancelled) return;
        setWorkorder(wo);

        // Run initial exception check against loaded data
        checkExceptions(wo);

        const lockStatus = await tryAcquire();
        if (cancelled) return;
        if (!lockStatus.locked) {
          setLockedByOther(true);
          setLockOwner(lockStatus.owner ?? '未知');
        }
      } catch (e: any) {
        if (cancelled) return;
        setError(e.message ?? '加载工单失败');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [workorderId]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- form ready handler (imperative tracking setup) ------------------
  // We set up change-tracking and exception-checking effects imperatively
  // on the Formily form, rather than calling useChangeTracker as a hook,
  // because the Form instance is not available until onFormReady fires.
  const handleFormReady = useCallback(
    (f: Form) => {
      setForm(f);

      // Initial values snapshot captured at form-ready time
      const initialValues = f.values as WorkOrderData;

      // --- change tracking (equivalent to useChangeTracker hook) ---------
      f.addEffects('changeTracker', () => {
        onFieldValueChange('*', (field: any) => {
          const path = field.path.toString();
          const initialValue = (initialValues as any)[path];
          const currentValue = field.value;
          const actuallyChanged = !isEqual(currentValue, initialValue);

          if (field.modified && actuallyChanged) {
            const existing = changesRef.current.findIndex(
              (c) => c.path === `/${path}`
            );
            const change: FieldChange = {
              op: 'replace',
              path: `/${path}`,
              field_label: field.title ?? path,
              old_value: initialValue,
              new_value: currentValue,
              ai_confidence: field.data?.aiConfidence ?? null,
            };
            if (existing >= 0) {
              changesRef.current[existing] = change;
            } else {
              changesRef.current.push(change);
            }
          } else if (field.modified && !actuallyChanged) {
            changesRef.current = changesRef.current.filter(
              (c) => c.path !== `/${path}`
            );
          }
        });

        onFormSubmit(() => {
          f.setFieldState('__changes__', (state: any) => {
            state.value = changesRef.current;
          });
        });
      });

      // --- real-time exception checking -----------------------------------
      f.addEffects('exceptionCheck', () => {
        onFieldValueChange('*', () => {
          checkExceptions(f.values as WorkOrderData);
        });
      });
    },
    [checkExceptions]
  );

  // ---- sync changesRef to state (for the drawer) ------------------------
  useEffect(() => {
    const interval = setInterval(() => {
      setChanges([...changesRef.current]);
    }, 500);
    return () => clearInterval(interval);
  }, []);

  // ---- submit flow ------------------------------------------------------
  const handleSubmit = useCallback(async () => {
    if (!workorder || !form) return;

    setSubmitting(true);
    try {
      // Re-check exceptions against current form values before submitting
      const currentExceptions = checkExceptions(
        form.values as WorkOrderData
      );
      if (currentExceptions.length > 0) {
        message.warning('仍有异常字段未修正，请修改后再提交');
        setSubmitting(false);
        setDrawerOpen(false);
        return;
      }

      await submitReview(workorderId, {
        session_id: sessionIdRef.current,
        version: workorder.version,
        changes: changesRef.current,
        reject_reason: null,
      });

      await tryRelease();
      message.success('审查完成');
      onNavigate?.('/workorders');
    } catch (e: any) {
      if (e instanceof ConflictError) {
        message.warning(e.message);
      } else {
        // Keep form data and session_id so the user can retry
        message.error('提交失败，请重试');
        setDrawerOpen(false);
      }
    } finally {
      setSubmitting(false);
    }
  }, [workorder, workorderId, form, checkExceptions, tryRelease, onNavigate]);

  // ---- reject flow ------------------------------------------------------
  const handleReject = useCallback(async () => {
    const reason = window.prompt('请输入退回原因：');
    if (!reason) return;

    setSubmitting(true);
    try {
      await submitReview(workorderId, {
        session_id: createSessionId(),
        version: workorder!.version,
        changes: [],
        reject_reason: reason,
      });

      await tryRelease();
      message.success('已退回重填');
      onNavigate?.('/workorders');
    } catch (e: any) {
      if (e instanceof ConflictError) {
        message.warning(e.message);
      } else {
        message.error('退回失败，请重试');
      }
    } finally {
      setSubmitting(false);
    }
  }, [workorder, workorderId, tryRelease, onNavigate]);

  // ---- render: loading --------------------------------------------------
  if (loading) {
    return (
      <Spin
        size="large"
        style={{ display: 'block', margin: '100px auto' }}
      />
    );
  }

  // ---- render: error ----------------------------------------------------
  if (error) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <p style={{ color: '#ff4d4f', fontSize: 16 }}>加载失败：{error}</p>
        <Button onClick={() => window.location.reload()}>刷新页面</Button>
      </div>
    );
  }

  if (!workorder) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <p>工单不存在</p>
        <Button onClick={() => onNavigate?.('/workorders')}>返回列表</Button>
      </div>
    );
  }

  // ---- render: main page ------------------------------------------------
  return (
    <div style={{ padding: 24, maxWidth: 1400, margin: '0 auto' }}>
      {/* Header */}
      <WorkOrderHeader workorder={workorder} />

      {/* Lock banner */}
      {lockedByOther && (
        <div
          style={{
            background: '#e6f7ff',
            border: '1px solid #91d5ff',
            padding: '8px 16px',
            borderRadius: 4,
            marginBottom: 16,
          }}
        >
          工单正由 {lockOwner} 审查中，当前为只读模式
        </div>
      )}

      {/* Exception alerts */}
      <ExceptionAlert exceptions={exceptions} />

      {/* Two-column layout */}
      <Row gutter={16}>
        <Col span={12}>
          <AiPreviewPanel workorder={workorder} />
        </Col>
        <Col span={12}>
          <EditFormPanel
            workorder={workorder}
            onFormReady={handleFormReady}
          />
        </Col>
      </Row>

      {/* Action buttons */}
      <div style={{ textAlign: 'center', marginTop: 24 }}>
        <Space>
          <Button
            type="primary"
            size="large"
            disabled={exceptions.length > 0 || lockedByOther}
            onClick={() => setDrawerOpen(true)}
          >
            确认提交
          </Button>
          <Button
            size="large"
            disabled={lockedByOther}
            onClick={handleReject}
          >
            退回重填
          </Button>
        </Space>
      </div>

      {/* Change preview drawer */}
      <ChangePreviewDrawer
        open={drawerOpen}
        changes={changes}
        onConfirm={handleSubmit}
        onCancel={() => setDrawerOpen(false)}
        loading={submitting}
      />
    </div>
  );
};

export default WorkOrderReviewPage;
