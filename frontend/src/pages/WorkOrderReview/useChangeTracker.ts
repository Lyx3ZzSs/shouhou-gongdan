// frontend/src/pages/WorkOrderReview/useChangeTracker.ts
import { useRef, useCallback } from 'react';
import { onFieldValueChange, onFormSubmit } from '@formily/core';
import type { Form } from '@formily/core';
import isEqual from 'lodash.isequal';
import type { FieldChange, WorkOrderData } from './types';

export function useChangeTracker(form: Form, initialValues: WorkOrderData) {
  const changesRef = useRef<FieldChange[]>([]);

  const setupTracker = useCallback(() => {
    form.addEffects('changeTracker', () => {
      onFieldValueChange('*', (field: any) => {
        const path = field.path.toString();
        const initialValue = initialValues[path];
        const currentValue = field.value;
        const actuallyChanged = !isEqual(currentValue, initialValue);

        if (field.modified && actuallyChanged) {
          const existing = changesRef.current.findIndex(c => c.path === `/${path}`);
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
            c => c.path !== `/${path}`
          );
        }
      });

      onFormSubmit(() => {
        form.setFieldState('__changes__', (state: any) => {
          state.value = changesRef.current;
        });
      });
    });
  }, [form, initialValues]);

  return { changesRef, setupTracker };
}
