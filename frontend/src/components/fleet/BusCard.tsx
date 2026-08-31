import type { BusStatus, FleetBus } from '@/types/domain';
import { timeAgo } from '@/lib/format';
import { getIcon } from '@/components/ui/icons';
import { cn } from '@/lib/cn';

const STATUS: Record<BusStatus, { label: string; dot: string; text: string }> = {
  active: { label: 'Active', dot: 'bg-emerald-500', text: 'text-emerald-600' },
  idle: { label: 'Idle', dot: 'bg-amber-500', text: 'text-amber-600' },
  offline: { label: 'Offline', dot: 'bg-slate-400', text: 'text-slate-500' },
  maintenance: { label: 'Maintenance', dot: 'bg-violet-500', text: 'text-violet-600' },
};

export function BusCard({ bus }: { bus: FleetBus }) {
  const st = STATUS[bus.status];
  const onlineCams = bus.cameras.filter((c) => c.online).length;
  const Bus = getIcon('bus');
  const Signal = getIcon('signal');
  const Video = getIcon('video');
  const Gps = getIcon(bus.gpsOnline ? 'wifi' : 'wifi-off');

  return (
    <div className="rounded-md border border-border-subtle bg-surface p-3.5 shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-md bg-command-900 text-brand-400">
            <Bus size={17} />
          </span>
          <div>
            <p className="text-[13px] font-semibold text-ink-900">{bus.label}</p>
            <p className="text-[11px] text-ink-500">{bus.routeName}</p>
          </div>
        </div>
        <span className={cn('flex items-center gap-1.5 text-[11px] font-semibold', st.text)}>
          <span className={cn('h-1.5 w-1.5 rounded-full', st.dot)} />
          {st.label}
        </span>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        <Stat label="Speed" value={`${bus.speedKmph}`} unit="km/h" />
        <Stat label="Events" value={`${bus.eventsToday}`} unit="today" />
        <Stat label="Coverage" value={`${bus.coverageKm}`} unit="km" />
      </div>

      <div className="mt-3 flex items-center justify-between border-t border-border-subtle pt-2.5 text-[11px] text-ink-500">
        <span className="flex items-center gap-1">
          <Video size={12} className={onlineCams === bus.cameras.length ? 'text-emerald-500' : 'text-amber-500'} />
          {onlineCams}/{bus.cameras.length} cams
        </span>
        <span className="flex items-center gap-1">
          <Gps size={12} className={bus.gpsOnline ? 'text-emerald-500' : 'text-slate-400'} />
          GPS
        </span>
        <span className="flex items-center gap-1">
          <Signal size={12} />
          {timeAgo(bus.lastPingAt)}
        </span>
      </div>
    </div>
  );
}

function Stat({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className="rounded-sm bg-surface-muted py-1.5">
      <p className="tnum text-[15px] font-semibold text-ink-900">{value}</p>
      <p className="text-[9px] uppercase tracking-wide text-ink-400">
        {label} · {unit}
      </p>
    </div>
  );
}
