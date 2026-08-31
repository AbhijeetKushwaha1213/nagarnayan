import type { ReactNode } from 'react';
import { CATEGORY_META, CAMERA_LABEL } from '@/config/taxonomy';
import { ROUTE_NAME_LOOKUP } from '@/mock/events';
import type { UrbanEvent } from '@/types/domain';
import { dateTime } from '@/lib/format';
import { getIcon } from '@/components/ui/icons';
import { ConfidenceBar } from './ConfidenceBar';
import { SeverityBadge, StatusBadge } from './badges';

interface EventDetailPanelProps {
  event: UrbanEvent | null;
  onClose?: () => void;
  /** dark = rendered over the map chrome */
  variant?: 'light' | 'dark';
}

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-[10px] font-medium uppercase tracking-wide text-ink-400">
        {label}
      </dt>
      <dd className="mt-0.5 text-[13px] font-medium text-ink-900">{value}</dd>
    </div>
  );
}

export function EventDetailPanel({ event, onClose }: EventDetailPanelProps) {
  if (!event) {
    const Empty = getIcon('crosshair');
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
        <span className="grid h-12 w-12 place-items-center rounded-full bg-surface-muted text-ink-400">
          <Empty size={22} />
        </span>
        <div>
          <p className="text-[13px] font-semibold text-ink-700">No event selected</p>
          <p className="mt-1 text-[12px] text-ink-500">
            Select a marker or a feed item to inspect the detection, its evidence
            frame and recommended action.
          </p>
        </div>
      </div>
    );
  }

  const cat = CATEGORY_META[event.category];
  const CatIcon = getIcon(cat.icon);
  const Cam = getIcon('video');
  const Pin = getIcon('map-pin');
  const Clock = getIcon('clock');
  const Bus = getIcon('bus');

  return (
    <div className="flex h-full flex-col animate-fade-in">
      <div className="flex items-start justify-between gap-3 border-b border-border-subtle px-4 py-3.5">
        <div className="flex items-center gap-2.5">
          <span
            className="grid h-9 w-9 place-items-center rounded-md"
            style={{ backgroundColor: `${cat.color}14`, color: cat.color }}
          >
            <CatIcon size={18} />
          </span>
          <div>
            <h3 className="text-[14px] font-semibold leading-tight text-ink-900">
              {event.title}
            </h3>
            <p className="text-[11px] text-ink-500">
              {cat.label} · {event.id}
            </p>
          </div>
        </div>
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-ink-400 transition-colors hover:bg-surface-muted hover:text-ink-700"
            aria-label="Close event details"
          >
            {(() => {
              const X = getIcon('x');
              return <X size={16} />;
            })()}
          </button>
        ) : null}
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        <div className="flex items-center gap-2">
          <SeverityBadge severity={event.severity} />
          <StatusBadge status={event.status} />
        </div>

        {/* Evidence frame placeholder */}
        <div className="relative mt-3.5 aspect-video w-full overflow-hidden rounded-md border border-command-700 bg-command-900">
          <div className="absolute inset-0 grid place-items-center text-command-600">
            <div className="flex flex-col items-center gap-1.5">
              <Cam size={26} />
              <span className="text-[11px] font-medium text-slate-400">
                Evidence frame
              </span>
            </div>
          </div>
          <div className="absolute left-2 top-2 flex items-center gap-1.5 rounded bg-black/50 px-1.5 py-0.5 text-[10px] font-medium text-slate-200 backdrop-blur">
            <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
            {CAMERA_LABEL[event.source.cameraId]}
          </div>
          <div className="tnum absolute bottom-2 right-2 rounded bg-black/50 px-1.5 py-0.5 text-[10px] text-slate-300 backdrop-blur">
            {event.location.latitude.toFixed(4)}, {event.location.longitude.toFixed(4)}
          </div>
        </div>

        <div className="mt-4">
          <p className="text-[10px] font-medium uppercase tracking-wide text-ink-400">
            AI Confidence
          </p>
          <div className="mt-1.5">
            <ConfidenceBar confidence={event.confidence} />
          </div>
        </div>

        {event.note ? (
          <p className="mt-4 rounded-md bg-surface-muted px-3 py-2.5 text-[12px] leading-relaxed text-ink-700">
            {event.note}
          </p>
        ) : null}

        <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3.5">
          <Field
            label="Location"
            value={
              <span className="flex items-center gap-1.5">
                <Pin size={13} className="text-ink-400" />
                {event.location.address}
              </span>
            }
          />
          <Field label="Zone" value={event.location.zone} />
          <Field
            label="Detected"
            value={
              <span className="flex items-center gap-1.5">
                <Clock size={13} className="text-ink-400" />
                {dateTime(event.timestamp)}
              </span>
            }
          />
          <Field
            label="Source"
            value={
              <span className="flex items-center gap-1.5">
                <Bus size={13} className="text-ink-400" />
                {event.source.busLabel}
              </span>
            }
          />
          <Field label="Camera" value={CAMERA_LABEL[event.source.cameraId]} />
          <Field
            label="Route"
            value={ROUTE_NAME_LOOKUP[event.source.routeId] ?? event.source.routeId}
          />
        </dl>
      </div>

      <div className="flex items-center gap-2 border-t border-border-subtle px-4 py-3">
        <button
          type="button"
          className="flex-1 rounded-sm bg-command-900 px-3 py-2 text-[12px] font-semibold text-white transition-colors hover:bg-command-800"
        >
          Dispatch Crew
        </button>
        <button
          type="button"
          className="rounded-sm border border-border-strong px-3 py-2 text-[12px] font-semibold text-ink-700 transition-colors hover:bg-surface-muted"
        >
          Mark Reviewed
        </button>
      </div>
    </div>
  );
}
