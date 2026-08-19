import { BarChart3, CheckSquare2, ClipboardList, UserRound } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/auth';

export type PlatformView = 'overview' | 'ledger' | 'workbench' | 'later' | 'search' | 'stats' | 'sync';

const items = [
  { id: 'ledger', label: '工单台账', icon: ClipboardList },
  { id: 'stats', label: '审核统计', icon: BarChart3 },
] as const;

export function PlatformNav({ active, onNavigate }: { active: PlatformView; onNavigate: (view: PlatformView) => void }) {
  const { user } = useAuth();
  return (
    <aside className="hidden h-full w-[220px] shrink-0 flex-col border-r border-border bg-background lg:flex">
      <div className="flex h-[88px] items-center gap-3 border-b border-border px-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <CheckSquare2 className="h-5 w-5" />
        </div>
        <div>
          <div className="font-semibold tracking-tight">售后工单审核</div>
          <div className="text-xs text-muted-foreground">智能核对平台</div>
        </div>
      </div>
      <nav className="flex-1 space-y-1 p-3" aria-label="主导航">
        {items.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => onNavigate(id)}
            className={cn(
              'flex h-11 w-full items-center gap-3 rounded-md px-3 text-sm font-medium transition-colors',
              active === id ? 'bg-blue-50 text-primary' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
            )}
            aria-current={active === id ? 'page' : undefined}
          >
            <Icon className="h-[18px] w-[18px]" />{label}
          </button>
        ))}
      </nav>
      <div className="border-t border-border p-3">
        <div className="flex items-center gap-3 rounded-md px-3 py-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted"><UserRound className="h-4 w-4" /></div>
          <div className="min-w-0">
            <div className="truncate text-sm font-medium">{user?.name ?? '审核员'}</div>
            <div className="text-xs text-muted-foreground">当前用户</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
