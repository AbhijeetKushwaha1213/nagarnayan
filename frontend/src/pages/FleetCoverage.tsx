import { useState } from 'react';
import { useEvents, useFleet } from '@/services/hooks';
import { MetricCard } from '@/components/analytics/MetricCard';
import { MapPanel } from '@/components/map/MapPanel';
import { BusCard } from '@/components/fleet/BusCard';
import { Panel, PanelHeader } from '@/components/ui/Panel';
import { Skeleton } from '@/components/ui/Skeleton';
import { PageContainer } from '@/components/layout/Page';
import { defaultLayerState, type MapLayerState } from '@/components/map/MapFilters';
import { getIcon } from '@/components/ui/icons';

export function FleetCoverage() {
  const { data: fleet, isLoading } = useFleet();
  const { data: events } = useEvents();
  const [layers, setLayersState] = useState<MapLayerState>(() => ({
    ...defaultLayerState(),
    showFleet: true,
    showRoutes: true,
  }));
  const setLayers = (u: (p: MapLayerState) => MapLayerState) => setLayersState(u);

  if (isLoading || !fleet) {
    return (
      <PageContainer className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[92px] rounded-md" />
          ))}
        </div>
        <Skeleton className="h-[400px] rounded-md" />
      </PageContainer>
    );
  }

  const active = fleet.filter((b) => b.status === 'active').length;
  const totalCoverage = fleet.reduce((s, b) => s + b.coverageKm, 0);
  const camsOnline = fleet.reduce((s, b) => s + b.cameras.filter((c) => c.online).length, 0);
  const camsTotal = fleet.reduce((s, b) => s + b.cameras.length, 0);
  const camHealth = Math.round((camsOnline / camsTotal) * 100);
  const Bus = getIcon('bus');

  return (
    <PageContainer className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricCard label="Active Sensing Buses" value={active} unit={`/ ${fleet.length}`} icon="bus" tone="info" hint="live" />
        <MetricCard label="Road Covered" value={totalCoverage} unit="km" icon="radio" tone="healthy" hint="today" />
        <MetricCard label="Camera Health" value={camHealth} unit="%" icon="video" tone={camHealth > 90 ? 'healthy' : 'warning'} hint={`${camsOnline}/${camsTotal} online`} />
        <MetricCard label="City Coverage" value={82} unit="%" icon="crosshair" tone="healthy" hint="road network" />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <MapPanel
          className="h-[440px] xl:col-span-2"
          title="Fleet & Sensing Coverage"
          events={events ?? []}
          fleet={fleet}
          layers={layers}
          setLayers={setLayers}
        />
        <Panel className="flex h-[440px] flex-col overflow-hidden">
          <PanelHeader title="Fleet Roster" subtitle={`${fleet.length} sensing units`} icon={<Bus size={15} />} />
          <div className="min-h-0 flex-1 space-y-2.5 overflow-y-auto p-3">
            {fleet.map((b) => (
              <BusCard key={b.id} bus={b} />
            ))}
          </div>
        </Panel>
      </div>
    </PageContainer>
  );
}
