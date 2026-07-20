import { PanelRightClose } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useReviewStore } from '../../store/useReviewStore';
import { CurrentChanges } from './CurrentChanges';
import { ReviewNotes } from './ReviewNotes';

export function ReviewSidebar() {
  const toggleRight = useReviewStore((s) => s.toggleRight);

  return (
    <aside className="flex h-full w-[340px] shrink-0 flex-col border-l border-border bg-background">
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border px-3">
        <span className="text-sm font-medium">审核控制台</span>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={toggleRight}
          aria-label="收起控制台"
          className="ml-auto"
        >
          <PanelRightClose className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex flex-1 flex-col divide-y divide-border overflow-y-auto">
        <CurrentChanges />
        <ReviewNotes />
      </div>
    </aside>
  );
}
