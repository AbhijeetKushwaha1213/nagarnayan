import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { NAV_ITEMS } from '@/config/nav';
import { CITY } from '@/mock/city';
import { useCommandMetrics } from '@/services/hooks';
import { getIcon } from '@/components/ui/icons';

function useClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

export function Header() {
  const { pathname } = useLocation();
  const now = useClock();
  const { data: metrics } = useCommandMetrics();

  const current =
    NAV_ITEMS.find((n) => (n.to === '/' ? pathname === '/' : pathname.startsWith(n.to))) ??
    NAV_ITEMS[0];

  const Search = getIcon('search');
  const Bell = getIcon('bell');
  const Siren = getIcon('siren');
  const critical = metrics?.criticalAlerts ?? 0;

  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b border-border-subtle bg-surface px-5">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <h1 className="truncate text-[15px] font-semibold tracking-tight text-ink-900">
            {current.label}
          </h1>
        </div>
        <p className="text-[11px] text-ink-500">
          {CITY.authority} · {CITY.name}
        </p>
      </div>

      {/* Search */}
      <div className="ml-4 hidden max-w-sm flex-1 items-center gap-2 rounded-sm border border-border-subtle bg-surface-muted px-2.5 py-1.5 text-ink-400 lg:flex">
        <Search size={14} />
        <input
          className="w-full bg-transparent text-[12px] text-ink-700 placeholder:text-ink-400 focus:outline-none"
          placeholder="Search location, event ID, or bus…"
        />
      </div>

      <div className="ml-auto flex items-center gap-3">
        {critical > 0 ? (
          <div className="flex items-center gap-1.5 rounded-sm bg-critical-soft px-2.5 py-1.5 text-[12px] font-semibold text-critical">
            <Siren size={14} />
            {critical} Critical
          </div>
        ) : null}

        <div className="hidden text-right sm:block">
          <p className="tnum text-[13px] font-semibold leading-none text-ink-900">
            {now.toLocaleTimeString('en-US', { hour12: false })}
          </p>
          <p className="text-[10px] text-ink-500">
            {now.toLocaleDateString('en-US', {
              weekday: 'short',
              day: '2-digit',
              month: 'short',
            })}
          </p>
        </div>

        <button
          type="button"
          className="relative rounded-sm border border-border-subtle p-2 text-ink-500 transition-colors hover:bg-surface-muted hover:text-ink-700"
          aria-label="Alerts"
        >
          <Bell size={15} />
          {critical > 0 ? (
            <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-critical" />
          ) : null}
        </button>

        <div className="flex items-center gap-2 border-l border-border-subtle pl-3">
          <span className="grid h-8 w-8 place-items-center rounded-full bg-command-900 text-[11px] font-semibold text-white">
            OP
          </span>
          <div className="hidden leading-tight md:block">
            <p className="text-[12px] font-semibold text-ink-900">Operator</p>
            <p className="text-[10px] text-ink-500">Control Room</p>
          </div>
        </div>
      </div>
    </header>
  );
}
