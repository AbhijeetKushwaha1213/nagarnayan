import { NavLink } from 'react-router-dom';
import { NAV_ITEMS } from '@/config/nav';
import { getIcon } from '@/components/ui/icons';
import { cn } from '@/lib/cn';

/** Persistent dark command-surface sidebar. */
export function Sidebar() {
  const Logo = getIcon('crosshair');
  return (
    <aside className="on-dark flex h-full w-60 shrink-0 flex-col bg-command-950 text-slate-300">
      {/* Brand */}
      <div className="flex items-center gap-2.5 border-b border-white/5 px-4 py-4">
        <span className="grid h-9 w-9 place-items-center rounded-md bg-brand-500/15 text-brand-400 ring-1 ring-brand-500/30">
          <Logo size={18} strokeWidth={2.2} />
        </span>
        <div className="leading-tight">
          <p className="text-[14px] font-semibold tracking-tight text-white">
            Nagar Nayan
          </p>
          <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-brand-400/80">
            Eyes of the City
          </p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-2.5 py-3">
        {NAV_ITEMS.map((item) => {
          const Icon = getIcon(item.icon);
          return (
            <div key={item.to}>
              {item.section ? (
                <p className="px-2.5 pb-1.5 pt-3.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-600">
                  {item.section}
                </p>
              ) : null}
              <NavLink
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  cn(
                    'group relative mb-0.5 flex items-center gap-2.5 rounded-sm px-2.5 py-2 text-[13px] font-medium transition-colors',
                    isActive
                      ? 'bg-command-800 text-white'
                      : 'text-slate-400 hover:bg-command-850 hover:text-slate-200',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      className={cn(
                        'absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full bg-brand-400 transition-opacity',
                        isActive ? 'opacity-100' : 'opacity-0',
                      )}
                    />
                    <Icon
                      size={16}
                      strokeWidth={2}
                      className={cn(isActive ? 'text-brand-400' : 'text-slate-500 group-hover:text-slate-300')}
                    />
                    <span className="truncate">{item.label}</span>
                  </>
                )}
              </NavLink>
            </div>
          );
        })}
      </nav>

      {/* Fleet status footer */}
      <div className="border-t border-white/5 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
          </span>
          <span className="text-[11px] font-medium text-slate-400">
            Sensing network online
          </span>
        </div>
        <p className="mt-1 text-[10px] text-slate-600">Edge AI · v0.1 · Prayagraj</p>
      </div>
    </aside>
  );
}
