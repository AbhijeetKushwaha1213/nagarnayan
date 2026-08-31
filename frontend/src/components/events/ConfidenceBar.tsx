import { cn } from '@/lib/cn';
import { confidencePct } from '@/lib/format';

/** Compact AI confidence meter. */
export function ConfidenceBar({
  confidence,
  className,
  showLabel = true,
}: {
  confidence: number;
  className?: string;
  showLabel?: boolean;
}) {
  const pct = Math.round(confidence * 100);
  const tone =
    pct >= 90 ? '#059669' : pct >= 80 ? '#0891b2' : pct >= 70 ? '#d97706' : '#dc2626';
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: tone }}
        />
      </div>
      {showLabel ? (
        <span className="tnum shrink-0 text-[11px] font-semibold text-ink-700">
          {confidencePct(confidence)}
        </span>
      ) : null}
    </div>
  );
}
