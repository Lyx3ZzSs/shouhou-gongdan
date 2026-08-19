import { useEffect, useState } from 'react';
import { ChevronDown, ChevronLeft, ChevronRight, ClipboardList, Clock3, FileSearch, Loader2, RefreshCw, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { PlatformNav, type PlatformView } from '@/components/PlatformNav';
import {
  confirmSyncNotCreated,
  fetchAuditLogs,
  fetchSyncFailures,
  fetchWorkOrder,
  fetchWorkOrderList,
  fetchWorkOrderPage,
  reconcileSync,
  retrySync,
  type GeneratedAuditLogEntry,
  type GeneratedWorkOrderSummary,
  type SyncFailure,
} from '@/api/review';
import type { WorkOrderData } from '@/types/review';
import { QUEUE as MOCK_QUEUE, buildTicket } from '@/workbench/mock/mockData';
import ReviewWorkbench from '@/workbench/ReviewWorkbench';

const USE_MOCK_DATA = import.meta.env.DEV && import.meta.env.VITE_USE_MOCK_DATA === 'true';
const PAGE_SIZE = 10;
const STATUS_LABELS: Record<string, string> = {
  pending_review: '待审核',
  stashed: '稍后处理',
  confirmed: '已通过',
  rejected: '已驳回',
  returned: '已退回',
};
const STATUS_STYLES: Record<string, string> = {
  pending_review: 'text-primary',
  stashed: 'text-amber-600',
  confirmed: 'text-emerald-600',
  rejected: 'text-destructive',
  returned: 'text-amber-600',
};

const KEY_FIELDS = [
  ['caseAccountId', '场站编号'],
  ['projectName__c', '项目名称'],
  ['problemResponsible__c', '问题责任人'],
  ['feedbackUserName__c', '反馈人姓名'],
  ['feedbackUserContact__c', '反馈人联系方式'],
  ['caseDescription', '工单描述'],
] as const;

function ReadonlyDetail({ id, onClose }: { id: string | null; onClose: () => void }) {
  const [ticket, setTicket] = useState<WorkOrderData | null>(null);
  const [logs, setLogs] = useState<GeneratedAuditLogEntry[]>([]);
  useEffect(() => {
    if (!id) return;
    if (USE_MOCK_DATA) {
      const item = MOCK_QUEUE.find((candidate) => candidate.id === id) ?? MOCK_QUEUE[0];
      const mockTicket = buildTicket(item);
      const values = Object.fromEntries(mockTicket.fields.map((field) => [field.id, field.originalValue]));
      setTicket({
        ...values,
        id: item.id,
        version: 2,
        ticket_id: Number(item.serialNumber.match(/\d+$/)?.[0] ?? 0),
        review_status: 'confirmed',
        reviewed_by: '开发审核员',
        reviewed_at: '2026-08-18T10:20:00+08:00',
      } as unknown as WorkOrderData);
      setLogs([{
        session_id: 'mock-reviewed', operator_name: '开发审核员', operated_at: '2026-08-18T10:20:00+08:00',
        changes: [{ op: 'replace', path: '/caseAccountId', field_label: '场站编号', old_value: 'SPCZ202408210132', new_value: 'SPCZ202408210188' }],
      } as GeneratedAuditLogEntry]);
      return;
    }
    Promise.all([fetchWorkOrder(id), fetchAuditLogs(id)]).then(([data, entries]) => {
      setTicket(data);
      setLogs(entries);
    });
  }, [id]);
  const changes = logs.flatMap((session) => session.changes ?? []);

  return (
    <Dialog open={Boolean(id)} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>已审核工单 {ticket?.ticket_id ?? ''}</DialogTitle>
          <DialogDescription>
            审核员：{ticket?.reviewed_by ?? '--'} · 审核时间：{ticket?.reviewed_at ? new Date(ticket.reviewed_at).toLocaleString('zh-CN') : '--'}
          </DialogDescription>
        </DialogHeader>
        {!ticket ? <Loader2 className="mx-auto my-10 h-5 w-5 animate-spin" /> : (
          <div className="max-h-[68vh] space-y-5 overflow-y-auto">
            <section>
              <h3 className="mb-2 text-sm font-medium">最终关键字段</h3>
              <div className="overflow-hidden rounded-lg border border-border">
                {KEY_FIELDS.map(([key, label]) => (
                  <div key={key} className="grid grid-cols-[160px_1fr] border-b border-border last:border-b-0">
                    <div className="bg-muted/30 px-4 py-3 text-sm text-muted-foreground">{label}</div>
                    <div className="whitespace-pre-wrap px-4 py-3 text-sm">{String(ticket[key] ?? '--')}</div>
                  </div>
                ))}
              </div>
            </section>
            <section>
              <h3 className="mb-2 text-sm font-medium">最终字段 Diff</h3>
              {changes.length === 0 ? <p className="text-sm text-muted-foreground">本次审核未修改字段。</p> : (
                <div className="space-y-2">
                  {changes.map((change, index) => (
                    <div key={`${change.path}-${index}`} className="rounded-lg border border-border p-3 text-sm">
                      <div className="mb-1 font-medium">{change.field_label}</div>
                      <span className="text-muted-foreground line-through">{String(change.old_value ?? '--')}</span>
                      <span className="mx-2 text-muted-foreground">→</span>
                      <span className="font-medium text-success">{String(change.new_value ?? '--')}</span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function WorkOrderModule({
  view,
  onNavigate,
  onReview,
}: {
  view: 'ledger' | 'later' | 'search' | 'sync';
  onNavigate: (view: PlatformView) => void;
  onReview: (id: string) => void;
}) {
  const [items, setItems] = useState<GeneratedWorkOrderSummary[]>([]);
  const [failures, setFailures] = useState<SyncFailure[]>([]);
  const [keyword, setKeyword] = useState('');
  const [status, setStatus] = useState('pending_review');
  const [createdFrom, setCreatedFrom] = useState('');
  const [createdTo, setCreatedTo] = useState('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [reviewId, setReviewId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncConfirm, setSyncConfirm] = useState<{ failure: SyncFailure; mode: 'created' | 'not-created' } | null>(null);
  const [externalId, setExternalId] = useState('');
  const [syncBusy, setSyncBusy] = useState(false);

  const load = async (
    searchKeyword = keyword,
    targetPage = page,
    statusFilter = status,
    createdFromFilter = createdFrom,
    createdToFilter = createdTo,
  ) => {
    setLoading(true);
    setError(null);
    try {
      if (USE_MOCK_DATA) {
        if (view === 'sync') {
          setFailures([{
            id: 'wo-sync-demo', ticket_id: 202608180099, sync_attempts: 2,
            sync_last_error: '销售易接口超时，创建结果待核实', sync_status: 'uncertain',
            sync_external_id: null, reviewed_at: '2026-08-18T10:10:00+08:00',
          }]);
        } else if (view === 'ledger') {
          const filtered = MOCK_QUEUE.filter((item) => (
            (!searchKeyword || item.serialNumber.includes(searchKeyword) || item.title.includes(searchKeyword))
            && (!statusFilter || item.status === statusFilter)
            && (!createdFromFilter || item.createdAt.slice(0, 10) >= createdFromFilter)
            && (!createdToFilter || item.createdAt.slice(0, 10) <= createdToFilter)
          )).sort((a, b) => b.createdAt.localeCompare(a.createdAt));
          const offset = (targetPage - 1) * PAGE_SIZE;
          setTotal(filtered.length);
          setItems(filtered.slice(offset, offset + PAGE_SIZE).map((item) => {
            const ticket = buildTicket(item);
            const caseDescription = ticket.fields.find((field) => field.id === 'caseDescription')?.originalValue;
            return {
              id: item.id,
              ticket_id: Number(item.serialNumber.match(/\d+$/)?.[0] ?? 0),
              name: item.title,
              review_status: item.status,
              caseAccountId: 'SPCZ202408210132',
              bigCustShortName__c: '东京二区便利店',
              caseDescription: String(caseDescription ?? ''),
              caseSource: item.source,
              projectName__c: 'XSJH20260723012',
              created_at: item.createdAt,
            };
          }));
        } else {
          const source = view === 'later'
            ? MOCK_QUEUE.filter((item) => item.status === 'stashed')
            : MOCK_QUEUE.filter((item) => !searchKeyword || item.serialNumber.includes(searchKeyword));
          setItems(source.map((item) => ({
            id: item.id,
            ticket_id: Number(item.serialNumber.match(/\d+$/)?.[0] ?? 0),
            name: item.title,
            review_status: view === 'later' ? 'stashed' : 'confirmed',
            caseAccountId: null,
            bigCustShortName__c: null,
            created_at: item.createdAt,
          })));
        }
        return;
      }
      if (view === 'sync') setFailures(await fetchSyncFailures());
      else if (view === 'ledger') {
        const result = await fetchWorkOrderPage(
          statusFilter || undefined,
          searchKeyword.trim() || undefined,
          (targetPage - 1) * PAGE_SIZE,
          PAGE_SIZE,
          createdFromFilter || undefined,
          createdToFilter || undefined,
        );
        setItems(result.items);
        setTotal(result.total);
      } else {
        setItems(await fetchWorkOrderList(view === 'later' ? 'stashed' : 'reviewed', searchKeyword.trim() || undefined));
      }
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const defaultStatus = view === 'ledger' ? 'pending_review' : '';
    setKeyword(''); setStatus(defaultStatus); setCreatedFrom(''); setCreatedTo(''); setPage(1);
    void load('', 1, defaultStatus, '', '');
  }, [view]);

  const title = view === 'ledger' ? '工单台账' : view === 'later' ? '稍后处理' : view === 'search' ? '工单搜索' : '同步失败';
  const Icon = view === 'ledger' ? ClipboardList : view === 'later' ? Clock3 : view === 'search' ? Search : RefreshCw;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const goToPage = (nextPage: number) => {
    setPage(nextPage);
    void load(keyword, nextPage, status, createdFrom, createdTo);
  };

  return (
    <div className="flex h-screen bg-app">
      <PlatformNav active={view} onNavigate={onNavigate} />
      <main className={view === 'ledger' ? 'flex min-w-0 flex-1 flex-col overflow-hidden bg-background' : 'flex min-w-0 flex-1 flex-col overflow-hidden p-6 lg:p-10'}>
        <div className="flex min-h-0 w-full flex-1 flex-col">
          <div className={view === 'ledger' ? 'flex h-[72px] shrink-0 items-center gap-4 border-b border-border px-6' : 'flex flex-wrap items-center justify-between gap-4'}>
            <h1 className="flex items-center gap-2 text-2xl font-semibold"><Icon className="h-5 w-5 text-primary" />{title}</h1>
            {view === 'ledger' && (
              <Button
                variant="outline"
                className="gap-3 font-normal"
                onClick={() => { setStatus(''); setPage(1); void load(keyword, 1, '', createdFrom, createdTo); }}
              >
                全部工单<ChevronDown className="h-4 w-4 text-muted-foreground" />
              </Button>
            )}
            {view === 'ledger' && (
              <div className="ml-auto flex items-center gap-1">
                <Button variant="ghost" size="sm" className="gap-2" onClick={() => void load()}><RefreshCw className="h-4 w-4" />刷新</Button>
              </div>
            )}
            {view === 'search' && (
              <form className="flex w-full max-w-2xl flex-wrap gap-2" onSubmit={(event) => { event.preventDefault(); setPage(1); void load(keyword, 1, status); }}>
                <Input className="min-w-56 flex-1" value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="工单号、场站、客户或项目" aria-label="搜索工单" />
                <Button type="submit">查询</Button>
              </form>
            )}
          </div>

          {view === 'ledger' && (
            <form className="flex min-h-[68px] shrink-0 flex-wrap items-center gap-3 border-b border-border px-6 py-3" onSubmit={(event) => { event.preventDefault(); setPage(1); void load(keyword, 1, status, createdFrom, createdTo); }}>
              <Input className="w-[340px]" value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="工单号、场站、客户或项目" aria-label="搜索工单" />
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">创建时间</span>
                <Input type="date" value={createdFrom} max={createdTo || undefined} onChange={(event) => setCreatedFrom(event.target.value)} className="w-36" aria-label="创建开始日期" />
                <span className="text-muted-foreground">至</span>
                <Input type="date" value={createdTo} min={createdFrom || undefined} onChange={(event) => setCreatedTo(event.target.value)} className="w-36" aria-label="创建结束日期" />
              </div>
              <Select value={status || 'all'} onValueChange={(value) => setStatus(value === 'all' ? '' : value)}>
                <SelectTrigger className="w-40" aria-label="审核状态">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">审核状态：全部</SelectItem>
                  <SelectItem value="pending_review">待审核</SelectItem>
                  <SelectItem value="stashed">稍后处理</SelectItem>
                  <SelectItem value="confirmed">已通过</SelectItem>
                  <SelectItem value="returned">已退回</SelectItem>
                </SelectContent>
              </Select>
              <Button type="submit" className="ml-auto w-24">查询</Button>
              <Button type="button" variant="outline" className="w-24" onClick={() => { setKeyword(''); setStatus('pending_review'); setCreatedFrom(''); setCreatedTo(''); setPage(1); void load('', 1, 'pending_review', '', ''); }}>重置</Button>
            </form>
          )}

          {loading ? <Loader2 className="mx-auto mt-24 h-6 w-6 animate-spin text-primary" /> : error ? (
            <div className="mt-8 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{error}<Button variant="outline" size="sm" onClick={() => void load()} className="ml-3">重试</Button></div>
          ) : view === 'ledger' ? (
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-background">
              <div className="min-h-0 flex-1 overflow-auto">
                <table className={`w-full min-w-[1260px] table-fixed text-left text-sm ${items.length === PAGE_SIZE ? 'h-full' : ''}`}>
                  <thead className="sticky top-0 z-10 border-b border-border bg-[#f7f8fa] text-muted-foreground">
                    <tr>
                      <th className="w-14 px-4 py-3 text-center font-medium">序号</th>
                      <th className="w-12 px-3 py-3 text-center font-medium"><span className="sr-only">选中</span></th>
                      <th className="w-56 px-4 py-3 font-medium">工单主题</th>
                      <th className="w-44 px-4 py-3 font-medium">工单编号</th>
                      <th className="w-72 px-4 py-3 font-medium">工单描述</th>
                      <th className="w-28 px-4 py-3 font-medium">审核状态</th>
                      <th className="w-28 px-4 py-3 font-medium">工单来源</th>
                      <th className="w-44 px-4 py-3 font-medium">场站编号</th>
                      <th className="w-52 px-4 py-3 font-medium">项目名称</th>
                      <th className="w-36 px-4 py-3 font-medium">创建时间</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {items.map((item, index) => {
                      const editable = item.review_status === 'pending_review' || item.review_status === 'stashed' || item.review_status === 'returned';
                      const selected = reviewId === item.id || selectedId === item.id;
                      return (
                        <tr key={item.id} className={selected ? 'bg-blue-50' : 'hover:bg-muted/20'}>
                          <td className="px-4 py-4 text-center text-muted-foreground">{(page - 1) * PAGE_SIZE + index + 1}</td>
                          <td className="px-3 py-4 text-center">
                            <input
                              type="checkbox"
                              checked={selected}
                              onChange={() => editable
                                ? setReviewId(selected ? null : item.id)
                                : setSelectedId(selected ? null : item.id)}
                              aria-label={`选择工单 ${item.ticket_id}`}
                              className="h-4 w-4 rounded border-border accent-primary"
                            />
                          </td>
                          <td className="truncate px-4 py-4 font-medium text-primary" title={item.name ?? ''}>
                            <button type="button" className="max-w-full truncate text-left hover:underline" onClick={() => editable ? setReviewId(item.id) : setSelectedId(item.id)}>{item.name ?? '未命名工单'}</button>
                          </td>
                          <td className="truncate px-4 py-4 font-mono">{item.ticket_id}</td>
                          <td className="truncate px-4 py-4 text-muted-foreground" title={item.caseDescription ?? ''}>{item.caseDescription ?? '--'}</td>
                          <td className="whitespace-nowrap px-4 py-4"><span className={`font-medium ${STATUS_STYLES[item.review_status ?? ''] ?? 'text-muted-foreground'}`}>{STATUS_LABELS[item.review_status ?? ''] ?? item.review_status ?? '未知'}</span></td>
                          <td className="truncate px-4 py-4">{item.caseSource ?? '--'}</td>
                          <td className="truncate px-4 py-4 text-primary">{item.caseAccountId ?? '--'}</td>
                          <td className="truncate px-4 py-4 text-primary" title={item.projectName__c ?? ''}>{item.projectName__c ?? '--'}</td>
                          <td className="whitespace-nowrap px-4 py-4 text-muted-foreground">{item.created_at ? new Date(item.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '--'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {items.length === 0 && <p className="p-12 text-center text-sm text-muted-foreground">没有符合条件的工单。</p>}
              </div>
              <div className="flex h-14 shrink-0 items-center justify-between border-t border-border px-6 text-sm text-muted-foreground">
                <span>共 <span className="font-medium text-foreground">{total}</span> 条</span>
                <div className="flex items-center gap-2">
                  <span className="mr-2">{PAGE_SIZE} 条/页</span>
                  <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => goToPage(page - 1)} aria-label="上一页"><ChevronLeft className="h-4 w-4" /></Button>
                  <span className="min-w-16 text-center">{page} / {totalPages}</span>
                  <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => goToPage(page + 1)} aria-label="下一页"><ChevronRight className="h-4 w-4" /></Button>
                </div>
              </div>
            </div>
          ) : view === 'sync' ? (
            <div className="mt-8 space-y-3">
              {failures.length === 0 ? <p className="rounded-xl border border-border bg-card p-10 text-center text-muted-foreground">当前没有同步失败工单。</p> : failures.map((failure) => (
                <article key={failure.id} className="rounded-xl border border-border bg-card p-5">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <div className="font-medium">工单 {failure.ticket_id}</div>
                      <div className="mt-1 text-sm text-destructive">{failure.sync_last_error ?? '同步结果待核实'}</div>
                      <div className="mt-1 text-xs text-muted-foreground">已尝试 {failure.sync_attempts} 次 · 状态 {failure.sync_status}</div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {failure.sync_status === 'failed' && <Button size="sm" onClick={async () => { if (USE_MOCK_DATA) setFailures([]); else { await retrySync(failure.id); await load(); } }}>人工重试</Button>}
                      {failure.sync_status === 'uncertain' && (
                        <>
                          <Button size="sm" variant="outline" onClick={() => { setExternalId(''); setSyncConfirm({ failure, mode: 'created' }); }}>确认已创建</Button>
                          <Button size="sm" onClick={() => setSyncConfirm({ failure, mode: 'not-created' })}>确认未创建</Button>
                        </>
                      )}
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="mt-8 space-y-3">
              {items.length === 0 ? <p className="rounded-xl border border-border bg-card p-10 text-center text-muted-foreground">{view === 'later' ? '没有稍后处理的工单。' : '未找到已审核工单。'}</p> : items.map((item) => (
                <article key={item.id} className="flex flex-wrap items-center gap-4 rounded-xl border border-border bg-card p-5">
                  <div className="min-w-0 flex-1">
                    <div className="font-mono text-sm font-medium">{item.ticket_id}</div>
                    <div className="mt-1 truncate text-sm text-muted-foreground">{item.name ?? item.caseAccountId ?? '未命名工单'}</div>
                  </div>
                  {view === 'later' ? (
                    <Button size="sm" onClick={() => onReview(item.id)}>继续审核</Button>
                  ) : (
                    <Button size="sm" variant="outline" onClick={() => setSelectedId(item.id)} className="gap-2"><FileSearch className="h-4 w-4" />只读查看</Button>
                  )}
                </article>
              ))}
            </div>
          )}
        </div>
      </main>
      {(view === 'ledger' || view === 'search') && <ReadonlyDetail id={selectedId} onClose={() => setSelectedId(null)} />}
      {view === 'ledger' && reviewId && (
        <ReviewWorkbench
          drawer
          initialTicketId={reviewId}
          onNavigate={onNavigate}
          onClose={() => { setReviewId(null); void load(keyword, page, status); }}
        />
      )}
      <Dialog open={Boolean(syncConfirm)} onOpenChange={(open) => !open && setSyncConfirm(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{syncConfirm?.mode === 'created' ? '确认销售易已创建' : '确认销售易未创建'}</DialogTitle>
            <DialogDescription>
              工单 {syncConfirm?.failure.ticket_id}。此操作会记录人工对账结果。
            </DialogDescription>
          </DialogHeader>
          {syncConfirm?.mode === 'created' ? (
            <Input autoFocus value={externalId} onChange={(event) => setExternalId(event.target.value)} placeholder="请输入销售易工单号" aria-label="销售易工单号" />
          ) : (
            <p className="text-sm text-muted-foreground">确认后该工单将转为“同步失败”，可再次人工重试。</p>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setSyncConfirm(null)} disabled={syncBusy}>取消</Button>
            <Button
              disabled={syncBusy || (syncConfirm?.mode === 'created' && !externalId.trim())}
              onClick={async () => {
                if (!syncConfirm) return;
                setSyncBusy(true);
                try {
                  if (USE_MOCK_DATA) setFailures([]);
                  else if (syncConfirm.mode === 'created') await reconcileSync(syncConfirm.failure.id, externalId.trim());
                  else await confirmSyncNotCreated(syncConfirm.failure.id);
                  setSyncConfirm(null);
                  await load();
                } catch (reason) {
                  setError((reason as Error).message);
                } finally {
                  setSyncBusy(false);
                }
              }}
            >{syncBusy ? '处理中…' : '确认'}</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
