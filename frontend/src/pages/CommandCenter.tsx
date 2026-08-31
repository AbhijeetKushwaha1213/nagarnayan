import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { UrbanEvent } from '@/types/domain';
import { useCommandMetrics, useEvents, useFleet, useTraffic } from '@/services/hooks';
import { defaultLayerState, type MapLayerState } from '@/components/map/MapFilters';
import { MapPanel } from '@/components/map/MapPanel';
import { MetricCard } from '@/components/analytics/MetricCard';
import { EventCard } from '@/components/events/EventCard';
import { EventDetailPanel } from '@/components/events/EventDetailPanel';
import { Panel, PanelHeader } from '@/components/ui/Panel';
import { Skeleton } from '@/components/ui/Skeleton';
import { PageContainer } from '@/components/layout/Page';
import { TRAFFIC_LEVEL_META } from '@/config/taxonomy';
import { getIcon } from '@/components/ui/icons';

export function CommandCenter() {
  const navigate = useNavigate();
  const { data: events, isLoading: eventsLoading } = useEvents();
  const { data: fleet } = useFleet();
  const { data: metrics, isLoading: metricsLoading } = useCommandMetrics();
  const { data: traffic } = useTraffic();

  const [layers, setLayersState] = useState<MapLayerState>(defaultLayerState);
  const setLayers = (u: (p: MapLayerState) => MapLayerState) => setLayersState(u);
  const [selectedId, setSelectedId] = useState<string | undefined>();

  const selected = events?.find((e) => e.id === selectedId) ?? null;
  const criticalEvents = useMemo(
    () =>
      (events ?? [])
        .filter((e) => e.severity === 'critical' || e.severity === 'high')
        .slice(0, 8),
    [events],
  );

  const onSelect = (e: UrbanEvent) => setSelectedId((cur) => (cur === e.id ? undefined : e.id));

  const trafficLevel = metrics?.cityTrafficLevel ?? 'medium';
  const trafficMeta = TRAFFIC_LEVEL_META[trafficLevel];
  const ArrowRight = getIcon('arrow-right');

  return (
    <PageContainer className="flex flex-col gap-4">
      {/* Operational summary */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {metricsLoading || !metrics ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[92px] rounded-md" />
          ))
        ) : (
          <>
            <MetricCard
              label="Active Buses"
              value={metrics.activeBuses}
              unit={`/ ${metrics.totalBuses}`}
              icon="bus"
              tone="info"
              hint="sensing now"
            />
            <MetricCard
              label="Active Events"
              value={metrics.activeEvents}
              icon="activity"
              tone="neutral"
              delta={{ value: '+6 today', direction: 'up', positive: false }}
            />
            <MetricCard
              label="Critical Alerts"
              value={metrics.criticalAlerts}
              icon="siren"
              tone="critical"
              hint="need action"
            />
            <MetricCard
              label="Road Defects"
              value={metrics.roadDefects}
              icon="construction"
              tone="warning"
              hint="open"
            />
            <MetricCard
              label="Congestion Hotspots"
              value={metrics.congestionHotspots}
              icon="car-front"
              tone="warning"
              hint={
                <span style={{ color: trafficMeta.color }}>{trafficMeta.label} traffic</span>
              }
            />
            <MetricCard
              label="Fleet Coverage"
              value={metrics.fleetCoveragePct}
              unit="%"
              icon="radio"
              tone="healthy"
              hint="city roads today"
            />
          </>
        )}
      </div>

      {/* Map + event rail */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <MapPanel
          className="h-[520px] xl:col-span-2"
          events={events ?? []}
          fleet={fleet}
          layers={layers}
          setLayers={setLayers}
          selectedId={selectedId}
          onSelectEvent={onSelect}
          title="City Operations · Live"
        />

        <Panel className="flex h-[520px] flex-col overflow-hidden">
          {selected ? (
            <EventDetailPanel event={selected} onClose={() => setSelectedId(undefined)} />
          ) : (
            <>
              <PanelHeader
                title="Recent Events"
                subtitle="Live detections from the fleet"
                icon={(() => {
                  const I = getIcon('activity');
                  return <I size={15} />;
                })()}
                action={
                  <button
                    type="button"
                    onClick={() => navigate('/map')}
                    className="flex items-center gap-1 text-[11px] font-semibold text-brand-600 hover:text-brand-700"
                  >
                    Open map <ArrowRight size={12} />
                  </button>
                }
              />
              <div className="min-h-0 flex-1 divide-y divide-border-subtle overflow-y-auto">
                {eventsLoading
                  ? Array.from({ length: 6 }).map((_, i) => (
                      <div key={i} className="px-3.5 py-3">
                        <Skeleton className="h-10 w-full" />
                      </div>
                    ))
                  : (events ?? []).map((e) => (
                      <EventCard
                        key={e.id}
                        event={e}
                        onSelect={onSelect}
                        active={e.id === selectedId}
                      />
                    ))}
              </div>
            </>
          )}
        </Panel>
      </div>

      {/* Recent critical events strip */}
      <Panel>
        <PanelHeader
          title="Recent Critical Events"
          subtitle="Highest-priority detections requiring operator attention"
          icon={(() => {
            const I = getIcon('siren');
            return <I size={15} />;
          })()}
        />
        <div className="grid grid-cols-1 gap-px bg-border-subtle sm:grid-cols-2 lg:grid-cols-4">
          {criticalEvents.map((e) => (
            <CriticalTile key={e.id} event={e} onClick={() => onSelect(e)} />
          ))}
        </div>
      </Panel>
    </PageContainer>
  );
}

function CriticalTile({ event, onClick }: { event: UrbanEvent; onClick: () => void }) {
  const sevColor = event.severity === 'critical' ? '#dc2626' : '#ea580c';
  const Pin = getIcon('map-pin');
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex flex-col gap-1.5 bg-surface px-4 py-3 text-left transition-colors hover:bg-surface-muted"
    >
      <div className="flex items-center justify-between">
        <span
          className="rounded-xs px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white"
          style={{ backgroundColor: sevColor }}
        >
          {event.severity}
        </span>
        <span className="tnum text-[10px] text-ink-400">
          {Math.round(event.confidence * 100)}% conf
        </span>
      </div>
      <p className="text-[13px] font-semibold text-ink-900">{event.title}</p>
      <p className="flex items-center gap-1 text-[11px] text-ink-500">
        <Pin size={11} className="text-ink-400" />
        {event.location.address}
      </p>
    </button>
  );
}
