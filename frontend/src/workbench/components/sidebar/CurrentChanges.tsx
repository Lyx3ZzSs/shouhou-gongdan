import { ArrowRight, Crosshair, Edit3, Undo2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useEffectiveChanges, useReviewStore } from '../../store/useReviewStore';
import { REASON_LABEL } from '../../lib/constants';
import { formatTime, formatValue } from '../../lib/format';

export function CurrentChanges() {
  const changes = useEffectiveChanges();
  const undoChange = useReviewStore((s) => s.undoChange);
  const locateField = useReviewStore((s) => s.locateField);

  return (
    <section className="flex flex-col">
      <div className="flex items-center gap-2 px-3 pb-2 pt-3">
        <Edit3 className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">本次变更</span>
        <Badge variant="muted" className="ml-auto tabular-nums">
          {changes.length}
        </Badge>
      </div>

      {changes.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-1.5 px-3 py-6 text-muted-foreground">
          <Edit3 className="h-5 w-5 opacity-40" />
          <span className="text-xs">暂无本次修改</span>
        </div>
      ) : (
        <ul className="flex flex-col">
          {changes.map((change) => (
            <li key={change.fieldId} className="border-t border-border/60 px-3 py-2">
              <div className="flex items-center gap-2">
                <span className="text-xs tabular-nums text-muted-foreground">
                  {formatTime(change.changedAt)}
                </span>
                <span
                  className="min-w-0 flex-1 truncate text-sm font-medium"
                  title={change.fieldName}
                >
                  {change.fieldName}
                </span>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => undoChange(change.fieldId)}
                  aria-label={`撤销修改：${change.fieldName}`}
                >
                  <Undo2 className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => locateField(change.fieldId)}
                  aria-label={`定位字段：${change.fieldName}`}
                >
                  <Crosshair className="h-3.5 w-3.5" />
                </Button>
              </div>

              <div className="mt-1 flex flex-wrap items-center gap-x-1 gap-y-0.5 text-sm">
                <span className="break-all text-muted-foreground line-through">
                  {formatValue(change.before)}
                </span>
                <ArrowRight className="h-3 w-3 shrink-0 text-muted-foreground" />
                <span className="break-all text-foreground">{formatValue(change.after)}</span>
              </div>

              <div className="mt-1">
                <Badge variant="muted">{REASON_LABEL[change.reason] ?? change.reason}</Badge>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
