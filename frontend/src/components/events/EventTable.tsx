import { CATEGORY_META } from '@/config/taxonomy';
import type { UrbanEvent } from '@/types/domain';
import { clockTime, confidencePct } from '@/lib/format';
import { getIcon } from '@/components/ui/icons';
import { SeverityBadge, StatusBadge } from './badges';

interface EventTableProps {
  events: UrbanEvent[];
  onSelect?: (event: UrbanEvent) => void;
  selectedId?: string;
}

/** Dense operational table for the intelligence pages. */
export function EventTable({ events, onSelect, selectedId }: EventTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left text-[12px]">
        <thead>
          <tr className="border-b border-border-subtle text-[10px] uppercase tracking-wide text-ink-400">
            <th className="px-4 py-2.5 font-semibold">Event</th>
            <th className="px-3 py-2.5 font-semibold">Location</th>
            <th className="px-3 py-2.5 font-semibold">Zone</th>
            <th className="px-3 py-2.5 font-semibold">Severity</th>
            <th className="px-3 py-2.5 font-semibold">Confidence</th>
            <th className="px-3 py-2.5 font-semibold">Source</th>
            <th className="px-3 py-2.5 font-semibold">Detected</th>
            <th className="px-3 py-2.5 font-semibold">Status</th>
          </tr>
        </thead>
        <tbody>
          {events.map((e) => {
            const cat = CATEGORY_META[e.category];
            const Icon = getIcon(cat.icon);
            const selected = e.id === selectedId;
            return (
              <tr
                key={e.id}
                onClick={() => onSelect?.(e)}
                className={`cursor-pointer border-b border-border-subtle/70 transition-colors hover:bg-surface-muted ${
                  selected ? 'bg-brand-50/70' : ''
                }`}
              >
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <span
                      className="grid h-6 w-6 shrink-0 place-items-center rounded"
                      style={{ backgroundColor: `${cat.color}14`, color: cat.color }}
                    >
                      <Icon size={13} strokeWidth={2} />
                    </span>
                    <span className="font-semibold text-ink-900">{e.title}</span>
                  </div>
                </td>
                <td className="px-3 py-2.5 text-ink-700">{e.location.address}</td>
                <td className="px-3 py-2.5 text-ink-500">{e.location.zone}</td>
                <td className="px-3 py-2.5">
                  <SeverityBadge severity={e.severity} />
                </td>
                <td className="tnum px-3 py-2.5 font-semibold text-ink-700">
                  {confidencePct(e.confidence)}
                </td>
                <td className="px-3 py-2.5 text-ink-500">{e.source.busId}</td>
                <td className="tnum px-3 py-2.5 text-ink-500">
                  {clockTime(e.timestamp)}
                </td>
                <td className="px-3 py-2.5">
                  <StatusBadge status={e.status} />
                </td>
              </tr>
            );
          })}
          {events.length === 0 ? (
            <tr>
              <td colSpan={8} className="px-4 py-10 text-center text-ink-400">
                No events match the current filters.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}
