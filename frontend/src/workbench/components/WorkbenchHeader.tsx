import {
  Bell,
  ChevronDown,
  Search,
  ShieldCheck,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { AutoSaveIndicator } from './primitives/AutoSaveIndicator';
import { useReviewStore, useQueueStats } from '../store/useReviewStore';
import { cn } from '@/lib/utils';

const NOTIFICATIONS = [
  { id: 'n1', text: 'WO-20260717-0379 即将超时（剩余 12 分钟）', tone: 'warning' as const },
  { id: 'n2', text: '李四转交 1 条工单给您', tone: 'info' as const },
  { id: 'n3', text: 'WO-20260717-0381 存在 1 个阻断错误', tone: 'danger' as const },
];

export function WorkbenchHeader() {
  const autoSaveStatus = useReviewStore((s) => s.autoSaveStatus);
  const setFilters = useReviewStore((s) => s.setFilters);
  const keyword = useReviewStore((s) => s.filters.keyword);
  const stats = useQueueStats();

  const processed = stats.processed;
  const total = processed + stats.pending;

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b bg-background px-4">
      {/* 产品名 */}
      <div className="flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <ShieldCheck className="h-4 w-4" />
        </div>
        <span className="text-[15px] font-semibold tracking-tight">工单审核工作台</span>
      </div>

      <Separator orientation="vertical" className="mx-1 h-6" />

      {/* 全局搜索 */}
      <div className="relative ml-2 w-72 max-w-[28vw]">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={keyword}
          onChange={(e) => setFilters({ keyword: e.target.value })}
          placeholder="搜索工单编号或标题"
          className="pl-8"
          aria-label="全局搜索工单"
        />
      </div>

      <div className="flex-1" />

      {/* 自动暂存 */}
      <AutoSaveIndicator status={autoSaveStatus} />

      <Separator orientation="vertical" className="h-6" />

      {/* 今日审核进度 */}
      <div className="flex items-center gap-1.5 text-xs">
        <span className="text-muted-foreground">今日审核</span>
        <span className="font-semibold tabular-nums text-foreground">
          {processed}
          <span className="text-muted-foreground"> / {total}</span>
        </span>
      </div>

      <Separator orientation="vertical" className="h-6" />

      {/* 通知 */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label="通知">
            <Bell className="h-4 w-4" />
            <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-destructive" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-80">
          <DropdownMenuLabel>通知（{NOTIFICATIONS.length}）</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {NOTIFICATIONS.map((n) => (
            <DropdownMenuItem key={n.id} className="items-start gap-2 py-2">
              <span
                className={cn(
                  'mt-1 h-1.5 w-1.5 shrink-0 rounded-full',
                  n.tone === 'danger' && 'bg-destructive',
                  n.tone === 'warning' && 'bg-warning',
                  n.tone === 'info' && 'bg-primary',
                )}
              />
              <span className="text-sm">{n.text}</span>
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      {/* 当前用户 */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
              张
            </span>
            <span className="text-sm">张三</span>
            <ChevronDown className="h-3.5 w-3.5 opacity-60" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-44">
          <DropdownMenuLabel>客户服务部 · 张三</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem>个人设置</DropdownMenuItem>
          <DropdownMenuItem>审核统计</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem className="text-destructive">退出登录</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
