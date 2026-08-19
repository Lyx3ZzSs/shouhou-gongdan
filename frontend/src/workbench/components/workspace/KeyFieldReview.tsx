import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Check, ChevronDown, FileSearch, RotateCcw, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import { formatValue, isEmpty } from '../../lib/format';
import { useReviewStore } from '../../store/useReviewStore';
import type { FieldDef } from '../../types';
import {
  fetchEmployeeOptions,
  fetchReviewContext,
  fetchStationOptions,
  type EmployeeOption,
  type ReviewContext,
  type StationOption,
} from '@/api/review';

export const KEY_FIELD_IDS = [
  'caseAccountId',
  'projectName__c',
  'problemResponsible__c',
  'feedbackUserName__c',
  'feedbackUserContact__c',
  'caseDescription',
] as const;

const FIELD_HELP: Record<string, string> = {
  caseAccountId: '销售易必填 · 场站编号，不是场站名称',
  projectName__c: '销售易必填 · 请与场站信息一并核对',
  problemResponsible__c: '销售易必填 · 提交北森员工编码',
  feedbackUserName__c: '选填',
  feedbackUserContact__c: '选填 · 填写时须为 11 位手机号',
  caseDescription: '选填',
};

const REQUIRED = new Set(['caseAccountId', 'projectName__c', 'problemResponsible__c']);

function FieldEditor({ field, onClose }: { field: FieldDef; onClose: () => void }) {
  const currentValue = useReviewStore((s) => s.fieldStates[field.id]?.currentValue);
  const setFieldValue = useReviewStore((s) => s.setFieldValue);
  const [value, setValue] = useState(String(currentValue ?? ''));
  const [stations, setStations] = useState<StationOption[]>([]);
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const phoneInvalid = field.id === 'feedbackUserContact__c' && value !== '' && !/^1\d{10}$/.test(value);
  const requiredInvalid = REQUIRED.has(field.id) && !value.trim();

  useEffect(() => {
    if (field.id === 'caseAccountId') fetchStationOptions(value).then(setStations).catch(() => setStations([]));
    if (field.id === 'problemResponsible__c') fetchEmployeeOptions(value).then(setEmployees).catch(() => setEmployees([]));
  }, [field.id]);

  const save = () => {
    if (phoneInvalid || requiredInvalid) return;
    setFieldValue(field.id, value, 'manual_correction');
    const station = stations.find((item) => item.case_account_id === value);
    if (station?.project_name) setFieldValue('projectName__c', station.project_name, 'station_linkage');
    const employee = employees.find((item) => item.job_number === value);
    if (employee?.dept_name) setFieldValue('problemDept__c', employee.dept_name, 'employee_linkage');
    onClose();
  };

  return (
    <div className="space-y-2">
      {field.type === 'textarea' ? (
        <Textarea
          autoFocus
          value={value}
          onChange={(event) => setValue(event.target.value)}
          className="min-h-24 resize-y bg-background"
        />
      ) : (
        <Input
          autoFocus
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') save();
            if (event.key === 'Escape') onClose();
          }}
          inputMode={field.id === 'feedbackUserContact__c' ? 'numeric' : undefined}
          list={field.id === 'caseAccountId' ? 'station-options' : field.id === 'problemResponsible__c' ? 'employee-options' : undefined}
          className="bg-background"
        />
      )}
      {field.id === 'caseAccountId' && (
        <datalist id="station-options">
          {stations.map((item) => <option key={item.case_account_id} value={item.case_account_id}>{item.station_name} · {item.project_name}</option>)}
        </datalist>
      )}
      {field.id === 'problemResponsible__c' && (
        <datalist id="employee-options">
          {employees.map((item) => <option key={item.job_number} value={item.job_number}>{item.name} · {item.dept_name}</option>)}
        </datalist>
      )}
      {(phoneInvalid || requiredInvalid) && (
        <p className="text-xs text-destructive" role="alert">
          {phoneInvalid ? '请输入 11 位手机号' : '此字段为销售易必填项'}
        </p>
      )}
      <div className="flex gap-2">
        <Button size="sm" onClick={save} disabled={phoneInvalid || requiredInvalid} className="gap-1.5">
          <Check className="h-3.5 w-3.5" />保存修改
        </Button>
        <Button size="sm" variant="ghost" onClick={onClose} className="gap-1.5">
          <X className="h-3.5 w-3.5" />取消
        </Button>
      </div>
    </div>
  );
}

function KeyFieldRow({ field }: { field: FieldDef }) {
  const state = useReviewStore((s) => s.fieldStates[field.id]);
  const ticketStatus = useReviewStore((s) => s.ticket?.status);
  const resetField = useReviewStore((s) => s.resetField);
  const [editing, setEditing] = useState(false);
  if (!state) return null;

  const readonly = field.readonly || ticketStatus === 'confirmed' || ticketStatus === 'rejected';
  const modified = state.status === 'modified';
  const missing = REQUIRED.has(field.id) && isEmpty(state.currentValue);

  return (
    <div
      id={`field-${field.id}`}
      className={cn(
        'grid grid-cols-[120px_minmax(0,1fr)] border-b border-border last:border-b-0 sm:grid-cols-[180px_minmax(0,1fr)] lg:grid-cols-[240px_minmax(0,1fr)]',
        modified && 'bg-blue-50/60',
        missing && 'bg-red-50/70',
      )}
    >
      <div className="px-3 py-4 sm:px-4 lg:px-5 lg:py-5">
        <div className="flex items-center gap-1.5 font-medium">
          {field.name}
          {REQUIRED.has(field.id) && <span className="text-destructive" aria-label="必填">*</span>}
        </div>
        {FIELD_HELP[field.id] && <p className="mt-1 text-xs leading-5 text-muted-foreground">{FIELD_HELP[field.id]}</p>}
      </div>

      <div className="border-l border-border px-3 py-4 sm:px-4 lg:px-5 lg:py-5">
        {editing ? (
          <FieldEditor field={field} onClose={() => setEditing(false)} />
        ) : (
          <div className="flex min-w-0 items-start gap-2 sm:gap-3">
            <div
              className={cn(
                'min-w-0 flex-1 rounded-md -m-1 p-1 outline-none',
                !readonly && 'cursor-text hover:bg-muted/40 focus-visible:ring-2 focus-visible:ring-ring',
              )}
              onDoubleClick={() => !readonly && setEditing(true)}
              onKeyDown={(event) => {
                if (!readonly && event.key === 'Enter') setEditing(true);
              }}
              role={readonly ? undefined : 'button'}
              tabIndex={readonly ? undefined : 0}
              aria-label={readonly ? undefined : `编辑${field.name}`}
              title={readonly ? undefined : '双击修改'}
            >
              {modified && <div className="mb-1 text-xs"><span className="rounded bg-primary/10 px-1.5 py-0.5 font-medium text-primary">已修改</span></div>}
              <div className={cn('break-words leading-6', modified && 'font-medium text-primary', missing && 'font-medium text-destructive')}>
                {missing ? '未填写' : formatValue(state.currentValue, field)}
              </div>
              {modified && (
                <div className="mt-2 text-xs text-muted-foreground">
                  原值：<span className="line-through decoration-destructive/40">{formatValue(field.originalValue, field)}</span>
                </div>
              )}
            </div>
            <div className="flex shrink-0 flex-col gap-1 sm:flex-row">
              {!readonly && modified && (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => resetField(field.id)}
                  aria-label={`恢复${field.name}原值`}
                  className="shrink-0 text-muted-foreground"
                >
                  <RotateCcw className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function KeyFieldReview() {
  const ticket = useReviewStore((s) => s.ticket);
  const [showOther, setShowOther] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [context, setContext] = useState<ReviewContext | null>(null);
  const [contextError, setContextError] = useState('');
  const fieldStates = useReviewStore((s) => s.fieldStates);
  const notes = useReviewStore((s) => s.notes);
  const setNotes = useReviewStore((s) => s.setNotes);
  const openSubmitDialog = useReviewStore((s) => s.openSubmitDialog);
  const fields = useMemo(() => {
    if (!ticket) return [];
    const byId = new Map(ticket.fields.map((field) => [field.id, field]));
    return KEY_FIELD_IDS.map((id) => byId.get(id)).filter((field): field is FieldDef => Boolean(field));
  }, [ticket]);
  const otherFields = ticket?.fields.filter((field) => !KEY_FIELD_IDS.includes(field.id as typeof KEY_FIELD_IDS[number])) ?? [];
  const editableOtherCount = otherFields.filter((field) => !field.readonly).length;
  const fieldValue = (id: string) => ticket?.fields.find((field) => field.id === id)?.originalValue;
  const blockers = ticket?.anomalies.filter((item) =>
    item.type === 'blocking_error' && (!item.fieldId || fieldStates[item.fieldId]?.status !== 'modified'),
  ) ?? [];
  const upstreamBlockers = blockers.filter((item) => !item.fieldId || !KEY_FIELD_IDS.includes(item.fieldId as typeof KEY_FIELD_IDS[number]));

  useEffect(() => {
    if (!evidenceOpen || !ticket) return;
    setContextError('');
    fetchReviewContext(ticket.id).then(setContext).catch((error: Error) => setContextError(error.message));
  }, [evidenceOpen, ticket?.id]);

  const rejectUpstream = () => {
    const reason = upstreamBlockers.map((item) => item.message).join('；');
    setNotes(notes.trim() ? `${notes}\n上游数据需补充：${reason}` : `上游数据需补充：${reason}`);
    openSubmitDialog('rejected');
  };

  return (
    <div className="mx-auto w-full max-w-[1180px] px-5 py-6 lg:px-8 lg:py-8">
      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="grid grid-cols-[120px_minmax(0,1fr)] border-b border-border bg-muted/35 px-0 text-xs font-medium text-muted-foreground sm:grid-cols-[180px_minmax(0,1fr)] lg:grid-cols-[240px_minmax(0,1fr)]">
          <div className="px-3 py-3 sm:px-4 lg:px-5">关键字段清单（{fields.length} 项）</div>
          <div className="border-l border-border px-3 py-3 sm:px-4 lg:px-5">核对值</div>
        </div>
        {fields.map((field) => <KeyFieldRow key={field.id} field={field} />)}
      </section>

      {blockers.length > 0 && (
        <section className="mt-4 rounded-lg border border-destructive/30 bg-destructive/[0.04] p-4" role="alert">
          <div className="flex items-center gap-2 font-medium text-destructive">
            <AlertTriangle className="h-4 w-4" />仍有 {blockers.length} 个阻断问题
          </div>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            {blockers.map((item) => <li key={item.id}>{item.message}</li>)}
          </ul>
          {upstreamBlockers.length > 0 && (
            <Button variant="destructive" size="sm" className="mt-3" onClick={rejectUpstream}>驳回上游补充</Button>
          )}
        </section>
      )}

      <button
        type="button"
        onClick={() => setShowOther((value) => !value)}
        className="mt-4 flex w-full items-center gap-2 rounded-lg border border-border bg-background px-4 py-3 text-left text-sm font-medium text-primary hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-expanded={showOther}
      >
        <ChevronDown className={cn('h-4 w-4 transition-transform', !showOther && '-rotate-90')} />
        {showOther ? '收起完整字段' : `查看其他 ${otherFields.length} 个字段`}
        <span className="ml-auto text-xs font-normal text-muted-foreground">
          {editableOtherCount} 项可编辑 · {otherFields.length - editableOtherCount} 项系统只读
        </span>
      </button>

      {showOther && (
        <section className="mt-2 overflow-hidden rounded-xl border border-border bg-card">
          <div className="grid grid-cols-[120px_minmax(0,1fr)] border-b border-border bg-muted/35 text-xs font-medium text-muted-foreground sm:grid-cols-[180px_minmax(0,1fr)] lg:grid-cols-[240px_minmax(0,1fr)]">
            <div className="px-3 py-3 sm:px-4 lg:px-5">完整字段清单</div>
            <div className="border-l border-border px-3 py-3 sm:px-4 lg:px-5">核对值 / 修改</div>
          </div>
          {otherFields.map((field) => <KeyFieldRow key={field.id} field={field} />)}
        </section>
      )}

      <div className="mt-4 flex items-center gap-3 text-sm text-muted-foreground">
        <Button variant="outline" size="sm" className="gap-2" onClick={() => setEvidenceOpen(true)}>
          <FileSearch className="h-4 w-4" />查看核对材料
        </Button>
        原始对话、附件与客户/项目台账按需查看
      </div>

      <Dialog open={evidenceOpen} onOpenChange={setEvidenceOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>核对材料</DialogTitle>
            <DialogDescription>整单材料集中展示，不与单个字段强绑定。</DialogDescription>
          </DialogHeader>
          <div className="max-h-[65vh] space-y-4 overflow-y-auto">
            <section className="rounded-lg border border-border p-4">
              <h3 className="text-sm font-medium">原始客服对话</h3>
              {contextError && <p className="mt-2 text-sm text-destructive">{contextError}</p>}
              {(context?.conversation.length ? context.conversation : [{ role: '工单描述', content: String(fieldValue('caseDescription') || '暂无内容') }]).map((item, index) => (
                <div key={`${item.role}-${index}`} className="mt-2 rounded-md bg-muted/40 px-3 py-2 text-sm leading-6">
                  <span className="mr-2 font-medium">{item.role}</span>{item.content}
                </div>
              ))}
            </section>
            <section className="rounded-lg border border-border p-4">
              <h3 className="text-sm font-medium">附件</h3>
              {context?.attachments.length ? context.attachments.map((item, index) => (
                <p key={`${item.file_path}-${index}`} className="mt-2 break-all text-sm">{item.file_name || item.file_path}</p>
              )) : <p className="mt-2 text-sm text-muted-foreground">{String(fieldValue('relatedAttachment__c') || '无附件')}</p>}
            </section>
            <section className="rounded-lg border border-border p-4">
              <h3 className="text-sm font-medium">客户 / 项目台账</h3>
              <dl className="mt-3 grid grid-cols-[120px_1fr] gap-y-2 text-sm">
                <dt className="text-muted-foreground">场站编号</dt><dd>{context?.ledger?.case_account_id || String(fieldValue('caseAccountId') || '--')}</dd>
                <dt className="text-muted-foreground">场站名称</dt><dd>{context?.ledger?.station_name || String(fieldValue('stationName') || '--')}</dd>
                <dt className="text-muted-foreground">项目名称</dt><dd>{context?.ledger?.project_name || String(fieldValue('projectName__c') || '--')}</dd>
                <dt className="text-muted-foreground">客户简称</dt><dd>{context?.ledger?.customer_name || String(fieldValue('bigCustShortName__c') || '--')}</dd>
                <dt className="text-muted-foreground">联系人</dt><dd>{context?.ledger?.name || '--'} {context?.ledger?.phone || ''}</dd>
              </dl>
            </section>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
