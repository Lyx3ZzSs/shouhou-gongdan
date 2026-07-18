import { useState } from 'react';
import { Check, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { REVIEW_REASONS } from '../../lib/constants';
import { formatValue } from '../../lib/format';
import { useReviewStore } from '../../store/useReviewStore';
import type { FieldDef } from '../../types';

/** 内联字段编辑：值输入 + 修改原因选择 + 确认/取消 */
export function FieldEditInline({ field }: { field: FieldDef }) {
  const fs = useReviewStore((s) => s.fieldStates[field.id]);
  const setFieldValue = useReviewStore((s) => s.setFieldValue);
  const setEditingField = useReviewStore((s) => s.setEditingField);

  const [value, setValue] = useState<unknown>(fs?.currentValue ?? field.originalValue);
  const [reason, setReason] = useState<string>(fs?.changeReason ?? 'manual_correction');

  const save = () => setFieldValue(field.id, value, reason);
  const cancel = () => setEditingField(null);

  const renderValueInput = () => {
    switch (field.type) {
      case 'select':
        return (
          <Select value={String(value ?? '')} onValueChange={(v) => setValue(v)}>
            <SelectTrigger className="h-8">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {field.options?.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      case 'textarea':
        return (
          <Textarea
            value={String(value ?? '')}
            onChange={(e) => setValue(e.target.value)}
            className="min-h-[64px]"
            autoFocus
          />
        );
      case 'datetime':
        return (
          <Input
            type="datetime-local"
            value={String(value ?? '').slice(0, 16)}
            onChange={(e) => setValue(e.target.value)}
            autoFocus
          />
        );
      case 'tags':
        return (
          <Input
            value={Array.isArray(value) ? (value as string[]).join('、') : String(value ?? '')}
            onChange={(e) =>
              setValue(e.target.value ? e.target.value.split('、').map((s) => s.trim()) : [])
            }
            placeholder="多个用、分隔"
            autoFocus
          />
        );
      default:
        return (
          <Input
            value={String(value ?? '')}
            onChange={(e) => setValue(e.target.value)}
            autoFocus={field.type !== 'number'}
            type={field.type === 'number' ? 'number' : 'text'}
          />
        );
    }
  };

  return (
    <div className="flex flex-col gap-1.5 py-1">
      {/* 编辑时显示原值对照 */}
      <div className="text-xs text-muted-foreground">
        原值：<span className="font-mono">{formatValue(field.originalValue, field)}</span>
      </div>
      {renderValueInput()}
      <div className="flex items-center gap-1.5">
        <Label htmlFor={`reason-${field.id}`} className="sr-only">
          修改原因
        </Label>
        <Select value={reason} onValueChange={setReason}>
          <SelectTrigger id={`reason-${field.id}`} className="h-7 flex-1 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {REVIEW_REASONS.map((r) => (
              <SelectItem key={r.value} value={r.value}>
                {r.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button size="sm" className="h-7 px-2" onClick={save}>
          <Check className="h-3.5 w-3.5" />
          确认
        </Button>
        <Button size="sm" variant="ghost" className="h-7 px-2" onClick={cancel}>
          <X className="h-3.5 w-3.5" />
          取消
        </Button>
      </div>
    </div>
  );
}
