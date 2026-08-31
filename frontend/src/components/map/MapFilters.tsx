import { CATEGORY_META } from '@/config/taxonomy';
import { CATEGORY_ORDER } from '@/mock/city';
import type { EventCategory } from '@/types/domain';
import { getIcon } from '@/components/ui/icons';
import { cn } from '@/lib/cn';

export interface MapLayerState {
  categories: Set<EventCategory>;
  showFleet: boolean;
  showRoutes: boolean;
}

export function defaultLayerState(): MapLayerState {
  return {
    categories: new Set<EventCategory>(CATEGORY_ORDER),
    showFleet: true,
    showRoutes: true,
  };
}

interface MapFiltersProps {
  state: MapLayerState;
  counts: Record<EventCategory, number>;
  onToggleCategory: (c: EventCategory) => void;
  onToggleFleet: () => void;
  onToggleRoutes: () => void;
  variant?: 'panel' | 'overlay';
}

function Toggle({
  active,
  color,
  icon,
  label,
  count,
  onClick,
}: {
  active: boolean;
  color: string;
  icon: string;
  label: string;
  count?: number;
  onClick: () => void;
}) {
  const Icon = getIcon(icon);
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex w-full items-center gap-2 rounded-sm border px-2.5 py-1.5 text-[12px] font-medium transition-colors',
        active
          ? 'border-command-600 bg-command-800 text-slate-100'
          : 'border-command-700/60 bg-transparent text-slate-500 hover:bg-command-800/50',
      )}
    >
      <span
        className="grid h-5 w-5 shrink-0 place-items-center rounded"
        style={{
          backgroundColor: active ? `${color}26` : 'transparent',
          color: active ? color : '#64748b',
        }}
      >
        <Icon size={13} />
      </span>
      <span className="truncate">{label}</span>
      {typeof count === 'number' ? (
        <span
          className={cn(
            'tnum ml-auto rounded px-1.5 py-0.5 text-[10px] font-semibold',
            active ? 'bg-command-700 text-slate-300' : 'bg-command-800/60 text-slate-500',
          )}
        >
          {count}
        </span>
      ) : null}
    </button>
  );
}

/** Layer/filter control rendered inside the dark map chrome. */
export function MapFilters({
  state,
  counts,
  onToggleCategory,
  onToggleFleet,
  onToggleRoutes,
}: MapFiltersProps) {
  return (
    <div className="on-dark flex flex-col gap-1.5">
      <p className="px-1 pb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        Event Layers
      </p>
      {CATEGORY_ORDER.map((c) => {
        const meta = CATEGORY_META[c];
        return (
          <Toggle
            key={c}
            active={state.categories.has(c)}
            color={meta.color}
            icon={meta.icon}
            label={meta.label}
            count={counts[c]}
            onClick={() => onToggleCategory(c)}
          />
        );
      })}
      <div className="my-1 h-px bg-command-700/60" />
      <p className="px-1 pb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        Fleet
      </p>
      <Toggle
        active={state.showFleet}
        color="#22d3ee"
        icon="bus"
        label="Bus Fleet"
        onClick={onToggleFleet}
      />
      <Toggle
        active={state.showRoutes}
        color="#38bdf8"
        icon="radio"
        label="Sensing Routes"
        onClick={onToggleRoutes}
      />
    </div>
  );
}
