import { PanelRightClose } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useReviewStore } from '../../store/useReviewStore';
import { CurrentChanges } from './CurrentChanges';
import { ReviewNotes } from './ReviewNotes';

export function ReviewSidebar() {
  const toggleRight = useReviewStore((s) => s.toggleRight);

  return (
    <aside className="flex h-full w-[340px] shrink-0 flex-col border-l border-border/40 bg-background/80 backdrop-blur-xl">
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border/30 px-3">
        <span className="text-sm font-medium tracking-tight">审核控制台</span>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={toggleRight}
          aria-label="收起控制台"
          className="ml-auto rounded-xl hover:bg-accent/50"
        >
          <PanelRightClose className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex flex-1 flex-col divide-y divide-border/30 overflow-y-auto">
        <CurrentChanges />
        <ReviewNotes />
      </div>
    </aside>
  );
}
