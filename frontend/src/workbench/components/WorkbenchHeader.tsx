import {
  ChevronDown,
  Search,
  ShieldCheck,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
import { useReviewStore } from '../store/useReviewStore';
import { useAuth } from '../../auth';

interface Props { onNavigateStats: () => void }

export function WorkbenchHeader({ onNavigateStats }: Props) {
  const autoSaveStatus = useReviewStore((s) => s.autoSaveStatus);
  const setFilters = useReviewStore((s) => s.setFilters);
  const keyword = useReviewStore((s) => s.filters.keyword);
  const { user, logout } = useAuth();

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border/40 bg-background/80 backdrop-blur-xl px-4">
      {/* 品牌标识 */}
      <div className="flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 border border-primary/20 backdrop-blur-sm">
          <ShieldCheck className="h-4 w-4 text-primary" />
        </div>
        <span className="text-[15px] font-semibold tracking-tight bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
          工单审核工作台
        </span>
      </div>

      <Separator orientation="vertical" className="mx-1 h-6" />

      {/* 全局搜索 */}
      <div className="relative ml-2 w-72 max-w-[28vw]">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/60" />
        <Input
          value={keyword}
          onChange={(e) => setFilters({ keyword: e.target.value })}
          placeholder="搜索工单编号或标题"
          className="pl-8 bg-muted/40 backdrop-blur-sm border-transparent focus:border-ring/30 focus:bg-background/80 rounded-xl transition-all duration-300"
          aria-label="全局搜索工单"
        />
      </div>

      <div className="flex-1" />

      {/* 自动暂存 */}
      <AutoSaveIndicator status={autoSaveStatus} />

      {/* 当前用户 */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary ring-2 ring-primary/20 shadow-sm">
              {user?.name?.charAt(0) ?? '?'}
            </span>
            <span className="text-sm">{user?.name ?? '未知用户'}</span>
            <ChevronDown className="h-3.5 w-3.5 opacity-60" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-44">
          <DropdownMenuLabel>{user?.department_name ?? ''} · {user?.name ?? ''}</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem>个人设置</DropdownMenuItem>
          <DropdownMenuItem onClick={onNavigateStats}>审核统计</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem className="text-destructive" onClick={logout}>退出登录</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
