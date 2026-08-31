import { useEffect, useMemo } from 'react';
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet';
import type { FleetBus, UrbanEvent } from '@/types/domain';
import { CITY, ROUTE_PATHS } from '@/mock/city';
import { CATEGORY_META } from '@/config/taxonomy';
import { clockTime, confidencePct } from '@/lib/format';
import { busIcon, eventIcon } from './markers';
import type { MapLayerState } from './MapFilters';

interface CityMapProps {
  events: UrbanEvent[];
  fleet?: FleetBus[];
  layers: MapLayerState;
  selectedId?: string;
  onSelectEvent?: (e: UrbanEvent) => void;
  className?: string;
  /** override initial zoom */
  zoom?: number;
}

/** Pans to the selected event without changing zoom abruptly. */
function FlyToSelected({ event }: { event?: UrbanEvent }) {
  const map = useMap();
  useEffect(() => {
    if (event) {
      map.flyTo([event.location.latitude, event.location.longitude], Math.max(map.getZoom(), 15), {
        duration: 0.6,
      });
    }
  }, [event, map]);
  return null;
}

export function CityMap({
  events,
  fleet = [],
  layers,
  selectedId,
  onSelectEvent,
  className,
  zoom = CITY.defaultZoom,
}: CityMapProps) {
  const visibleEvents = useMemo(
    () => events.filter((e) => layers.categories.has(e.category)),
    [events, layers.categories],
  );
  const selected = events.find((e) => e.id === selectedId);

  return (
    <div className={className}>
      <MapContainer
        center={CITY.center}
        zoom={zoom}
        zoomControl
        className="h-full w-full"
        preferCanvas
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
          subdomains="abcd"
          maxZoom={20}
        />

        {layers.showRoutes
          ? Object.entries(ROUTE_PATHS).map(([id, path]) => (
              <Polyline
                key={id}
                positions={path}
                pathOptions={{
                  color: '#38bdf8',
                  weight: 2,
                  opacity: 0.35,
                  dashArray: '4 6',
                }}
              />
            ))
          : null}

        {visibleEvents.map((e) => (
          <Marker
            key={e.id}
            position={[e.location.latitude, e.location.longitude]}
            icon={eventIcon(e.category, e.severity)}
            eventHandlers={{ click: () => onSelectEvent?.(e) }}
            zIndexOffset={e.severity === 'critical' ? 1000 : 0}
          >
            <Popup>
              <div className="min-w-[180px]">
                <p className="text-[12px] font-semibold text-white">{e.title}</p>
                <p className="mt-0.5 text-[11px] text-slate-400">
                  {e.location.address} · {e.location.zone}
                </p>
                <div className="mt-1.5 flex items-center gap-2 text-[11px] text-slate-300">
                  <span
                    className="rounded px-1 py-0.5 text-[10px] font-semibold"
                    style={{
                      backgroundColor: `${CATEGORY_META[e.category].color}33`,
                      color: CATEGORY_META[e.category].color,
                    }}
                  >
                    {CATEGORY_META[e.category].label}
                  </span>
                  <span>{confidencePct(e.confidence)} conf</span>
                  <span>·</span>
                  <span>{clockTime(e.timestamp)}</span>
                </div>
              </div>
            </Popup>
          </Marker>
        ))}

        {layers.showFleet
          ? fleet.map((b) => (
              <Marker
                key={b.id}
                position={[b.location.latitude, b.location.longitude]}
                icon={busIcon(b.heading, b.status === 'active')}
              >
                <Popup>
                  <div className="min-w-[160px]">
                    <p className="text-[12px] font-semibold text-white">{b.label}</p>
                    <p className="mt-0.5 text-[11px] text-slate-400">{b.routeName}</p>
                    <div className="mt-1.5 text-[11px] text-slate-300">
                      {b.status.toUpperCase()} · {b.speedKmph} km/h · {b.eventsToday} events today
                    </div>
                  </div>
                </Popup>
              </Marker>
            ))
          : null}

        <FlyToSelected event={selected} />
      </MapContainer>
    </div>
  );
}
