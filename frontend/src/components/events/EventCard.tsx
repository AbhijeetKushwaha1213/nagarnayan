import { CATEGORY_META, SEVERITY_META } from '@/config/taxonomy';
import type { UrbanEvent } from '@/types/domain';
import { cn } from '@/lib/cn';
import { confidencePct, timeAgo } from '@/lib/format';
import { getIcon } from '@/components/ui/icons';
import { SeverityBadge } from './badges';

interface EventCardProps {
  event: UrbanEvent;
  onSelect?: (event: UrbanEvent) => void;
  active?: boolean;
  className?: string;
}

/** Row used in event feeds. Left rail is tinted by severity for fast triage. */
export function EventCard({ event, onSelect, active, className }: EventCardProps) {
  const cat = CATEGORY_META[event.category];
  const sev = SEVERITY_META[event.severity];
  const Icon = getIcon(cat.icon);

  return (
    <button
      type="button"
      onClick={() => onSelect?.(event)}
      className={cn(
        'group relative flex w-full items-start gap-3 border-l-2 px-3.5 py-3 text-left transition-colors',
        'hover:bg-surface-muted',
        active ? 'bg-brand-50/70' : 'bg-transparent',
        className,
      )}
      style={{ borderLeftColor: sev.color }}
    >
      <span
        className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-md"
        style={{ backgroundColor: `${cat.color}14`, color: cat.color }}
      >
        <Icon size={16} strokeWidth={2} />
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-[13px] font-semibold text-ink-900">
            {event.title}
          </span>
          <SeverityBadge severity={event.severity} />
        </div>

        <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-ink-500">
          <span className="truncate">{event.location.address}</span>
          <span className="text-ink-400">·</span>
          <span className="shrink-0">{event.location.zone}</span>
        </div>

        <div className="mt-1.5 flex items-center gap-3 text-[11px] text-ink-500">
          <span className="tnum">
            Conf <span className="font-semibold text-ink-700">{confidencePct(event.confidence)}</span>
          </span>
          <span className="text-ink-300">·</span>
          <span className="truncate">{event.source.busLabel}</span>
          <span className="ml-auto shrink-0 tnum text-ink-400">
            {timeAgo(event.timestamp)}
          </span>
        </div>
      </div>
    </button>
  );
}
