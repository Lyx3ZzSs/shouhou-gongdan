import { StickyNote } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { useReviewStore } from '../../store/useReviewStore';
import { NOTE_PHRASES } from '../../lib/constants';

export function ReviewNotes() {
  const notes = useReviewStore((s) => s.notes);
  const setNotes = useReviewStore((s) => s.setNotes);
  const appendNotePhrase = useReviewStore((s) => s.appendNotePhrase);

  return (
    <section className="flex flex-col">
      <div className="flex items-center gap-2 px-3 pb-2 pt-3">
        <StickyNote className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">审核备注</span>
      </div>

      <div className="px-3 pb-3">
        <Textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="填写审核备注…"
          className="min-h-[80px] resize-y"
          aria-label="审核备注"
        />

        <div className="mt-3">
          <div className="mb-1.5 text-xs text-muted-foreground">常用短语</div>
          <div className="flex flex-wrap gap-1.5">
            {NOTE_PHRASES.map((phrase) => (
              <Button
                key={phrase}
                variant="outline"
                size="sm"
                onClick={() => appendNotePhrase(phrase)}
              >
                {phrase}
              </Button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
