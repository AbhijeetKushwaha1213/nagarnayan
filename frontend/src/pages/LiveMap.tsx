import { useMemo, useState } from 'react';
import type { EventCategory } from '@/types/domain';
import { useEvents, useFleet } from '@/services/hooks';
import { CATEGORY_ORDER } from '@/mock/city';
import {
  defaultLayerState,
  MapFilters,
  type MapLayerState,
} from '@/components/map/MapFilters';
import { CityMap } from '@/components/map/CityMap';
import { EventDetailPanel } from '@/components/events/EventDetailPanel';
import { EventCard } from '@/components/events/EventCard';
import { getIcon } from '@/components/ui/icons';

export function LiveMap() {
  const { data: events } = useEvents();
  const { data: fleet } = useFleet();
  const [layers, setLayers] = useState<MapLayerState>(defaultLayerState);
  const [selectedId, setSelectedId] = useState<string | undefined>();
  const [query, setQuery] = useState('');

  const selected = events?.find((e) => e.id === selectedId) ?? null;

  const counts = useMemo(() => {
    return CATEGORY_ORDER.reduce(
      (acc, c) => {
        acc[c] = (events ?? []).filter((e) => e.category === c).length;
        return acc;
      },
      {} as Record<EventCategory, number>,
    );
  }, [events]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (events ?? [])
      .filter((e) => layers.categories.has(e.category))
      .filter(
        (e) =>
          !q ||
          e.title.toLowerCase().includes(q) ||
          e.location.address.toLowerCase().includes(q) ||
          e.location.zone.toLowerCase().includes(q) ||
          e.source.busId.toLowerCase().includes(q),
      );
  }, [events, layers.categories, query]);

  const toggleCategory = (c: EventCategory) =>
    setLayers((prev) => {
      const next = new Set(prev.categories);
      next.has(c) ? next.delete(c) : next.add(c);
      return { ...prev, categories: next };
    });

  const Search = getIcon('search');
  const Reset = getIcon('reset');

  return (
    <div className="flex h-full min-h-0">
      {/* Controls */}
      <div className="on-dark flex w-64 shrink-0 flex-col bg-command-950 text-slate-300">
        <div className="border-b border-white/5 p-3">
          <div className="flex items-center gap-2 rounded-sm bg-command-850 px-2.5 py-2 text-slate-400">
            <Search size={14} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search location or bus…"
              className="w-full bg-transparent text-[12px] text-slate-200 placeholder:text-slate-500 focus:outline-none"
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-3">
          <MapFilters
            state={layers}
            counts={counts}
            onToggleCategory={toggleCategory}
            onToggleFleet={() => setLayers((p) => ({ ...p, showFleet: !p.showFleet }))}
            onToggleRoutes={() => setLayers((p) => ({ ...p, showRoutes: !p.showRoutes }))}
          />
        </div>
        <div className="border-t border-white/5 p-3">
          <button
            type="button"
            onClick={() => {
              setLayers(defaultLayerState());
              setQuery('');
              setSelectedId(undefined);
            }}
            className="flex w-full items-center justify-center gap-1.5 rounded-sm border border-command-600 px-3 py-2 text-[12px] font-semibold text-slate-300 transition-colors hover:bg-command-800"
          >
            <Reset size={13} /> Reset View
          </button>
        </div>
      </div>

      {/* Map */}
      <div className="relative min-w-0 flex-1">
        <CityMap
          events={filtered}
          fleet={fleet}
          layers={layers}
          selectedId={selectedId}
          onSelectEvent={(e) => setSelectedId(e.id)}
          className="absolute inset-0"
        />
        <div className="pointer-events-none absolute left-3 top-3 z-[500] rounded-sm bg-command-950/85 px-2.5 py-1.5 text-[12px] font-semibold text-slate-100 ring-1 ring-white/10 backdrop-blur">
          <span className="tnum">{filtered.length}</span> events on map
        </div>
      </div>

      {/* Detail */}
      <div className="w-[340px] shrink-0 border-l border-border-subtle bg-surface">
        {selected ? (
          <EventDetailPanel event={selected} onClose={() => setSelectedId(undefined)} />
        ) : (
          <div className="flex h-full flex-col">
            <div className="border-b border-border-subtle px-4 py-3">
              <h3 className="text-[13px] font-semibold text-ink-900">Events</h3>
              <p className="text-[11px] text-ink-500">Select one to inspect details</p>
            </div>
            <div className="min-h-0 flex-1 divide-y divide-border-subtle overflow-y-auto">
              {filtered.map((e) => (
                <EventCard key={e.id} event={e} onSelect={(ev) => setSelectedId(ev.id)} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
