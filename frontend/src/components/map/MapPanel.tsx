import { useState } from 'react';
import type { FleetBus, UrbanEvent } from '@/types/domain';
import { CATEGORY_META } from '@/config/taxonomy';
import { CATEGORY_ORDER } from '@/mock/city';
import { getIcon } from '@/components/ui/icons';
import { cn } from '@/lib/cn';
import { CityMap } from './CityMap';
import { MapFilters, type MapLayerState } from './MapFilters';
import type { EventCategory } from '@/types/domain';

interface MapPanelProps {
  events: UrbanEvent[];
  fleet?: FleetBus[];
  layers: MapLayerState;
  setLayers: (updater: (prev: MapLayerState) => MapLayerState) => void;
  selectedId?: string;
  onSelectEvent?: (e: UrbanEvent) => void;
  className?: string;
  title?: string;
  showFilterToggle?: boolean;
}

/** Map + dark overlay chrome (title, live badge, legend, layer popover). */
export function MapPanel({
  events,
  fleet,
  layers,
  setLayers,
  selectedId,
  onSelectEvent,
  className,
  title = 'Live City Map',
  showFilterToggle = true,
}: MapPanelProps) {
  const [filtersOpen, setFiltersOpen] = useState(false);
  const Layers = getIcon('layers');

  const counts = CATEGORY_ORDER.reduce(
    (acc, c) => {
      acc[c] = events.filter((e) => e.category === c).length;
      return acc;
    },
    {} as Record<EventCategory, number>,
  );

  const toggleCategory = (c: EventCategory) =>
    setLayers((prev) => {
      const next = new Set(prev.categories);
      next.has(c) ? next.delete(c) : next.add(c);
      return { ...prev, categories: next };
    });

  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-md border border-command-700 bg-command-950',
        className,
      )}
    >
      <CityMap
        events={events}
        fleet={fleet}
        layers={layers}
        selectedId={selectedId}
        onSelectEvent={onSelectEvent}
        className="absolute inset-0"
      />

      {/* Title / live badge */}
      <div className="pointer-events-none absolute left-3 top-3 z-[500] flex items-center gap-2">
        <div className="pointer-events-auto flex items-center gap-2 rounded-sm bg-command-950/85 px-2.5 py-1.5 text-[12px] font-semibold text-slate-100 backdrop-blur ring-1 ring-white/10">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-500 opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-red-500" />
          </span>
          {title}
        </div>
      </div>

      {/* Layer control */}
      {showFilterToggle ? (
        <div className="absolute right-3 top-3 z-[500]">
          <button
            type="button"
            onClick={() => setFiltersOpen((v) => !v)}
            className={cn(
              'flex items-center gap-1.5 rounded-sm px-2.5 py-1.5 text-[12px] font-medium ring-1 ring-white/10 backdrop-blur transition-colors',
              filtersOpen
                ? 'bg-command-800 text-white'
                : 'bg-command-950/85 text-slate-300 hover:text-white',
            )}
          >
            <Layers size={14} />
            Layers
          </button>
          {filtersOpen ? (
            <div className="mt-2 w-56 rounded-md bg-command-950/95 p-2.5 shadow-2xl ring-1 ring-white/10 backdrop-blur">
              <MapFilters
                state={layers}
                counts={counts}
                onToggleCategory={toggleCategory}
                onToggleFleet={() => setLayers((p) => ({ ...p, showFleet: !p.showFleet }))}
                onToggleRoutes={() => setLayers((p) => ({ ...p, showRoutes: !p.showRoutes }))}
              />
            </div>
          ) : null}
        </div>
      ) : null}

      {/* Legend */}
      <div className="pointer-events-none absolute bottom-3 left-3 z-[500] flex flex-wrap gap-x-3 gap-y-1 rounded-sm bg-command-950/80 px-2.5 py-1.5 text-[10px] font-medium text-slate-300 ring-1 ring-white/10 backdrop-blur">
        {CATEGORY_ORDER.map((c) => (
          <span key={c} className="flex items-center gap-1.5">
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: CATEGORY_META[c].color }}
            />
            {CATEGORY_META[c].label}
          </span>
        ))}
      </div>
    </div>
  );
}
