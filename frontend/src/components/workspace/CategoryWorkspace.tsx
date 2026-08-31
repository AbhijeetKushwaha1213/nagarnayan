import { useMemo, useState } from 'react';
import type { EventCategory, UrbanEvent } from '@/types/domain';
import { useEvents, useFleet } from '@/services/hooks';
import { MetricCard, type MetricTone } from '@/components/analytics/MetricCard';
import { MapPanel } from '@/components/map/MapPanel';
import { EventTable } from '@/components/events/EventTable';
import { EventDetailPanel } from '@/components/events/EventDetailPanel';
import { Panel, PanelHeader } from '@/components/ui/Panel';
import { PageContainer } from '@/components/layout/Page';
import { defaultLayerState, type MapLayerState } from '@/components/map/MapFilters';
import { getIcon } from '@/components/ui/icons';

interface MetricDef {
  label: string;
  compute: (events: UrbanEvent[]) => number;
  icon: string;
  tone: MetricTone;
  unit?: string;
  hint?: string;
}

interface CategoryWorkspaceProps {
  categories: EventCategory[];
  tableTitle: string;
  tableIcon: string;
  metrics: MetricDef[];
  showFleet?: boolean;
}

/** Shared layout for the category-focused intelligence pages. */
export function CategoryWorkspace({
  categories,
  tableTitle,
  tableIcon,
  metrics,
  showFleet = false,
}: CategoryWorkspaceProps) {
  const { data: allEvents } = useEvents();
  const { data: fleet } = useFleet();
  const [selectedId, setSelectedId] = useState<string | undefined>();

  const catSet = useMemo(() => new Set(categories), [categories]);
  const events = useMemo(
    () => (allEvents ?? []).filter((e) => catSet.has(e.category)),
    [allEvents, catSet],
  );

  const [layers, setLayersState] = useState<MapLayerState>(() => ({
    ...defaultLayerState(),
    categories: new Set(categories),
    showFleet,
  }));
  const setLayers = (u: (p: MapLayerState) => MapLayerState) => setLayersState(u);

  const selected = events.find((e) => e.id === selectedId) ?? null;
  const TableIcon = getIcon(tableIcon);

  return (
    <PageContainer className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {metrics.map((m) => (
          <MetricCard
            key={m.label}
            label={m.label}
            value={m.compute(events)}
            unit={m.unit}
            icon={m.icon}
            tone={m.tone}
            hint={m.hint}
          />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <MapPanel
          className="h-[420px] xl:col-span-2"
          events={events}
          fleet={showFleet ? fleet : undefined}
          layers={layers}
          setLayers={setLayers}
          selectedId={selectedId}
          onSelectEvent={(e) => setSelectedId((c) => (c === e.id ? undefined : e.id))}
        />
        <Panel className="h-[420px] overflow-hidden">
          <EventDetailPanel event={selected} onClose={() => setSelectedId(undefined)} />
        </Panel>
      </div>

      <Panel>
        <PanelHeader title={tableTitle} icon={<TableIcon size={15} />} subtitle={`${events.length} detections`} />
        <EventTable events={events} onSelect={(e) => setSelectedId(e.id)} selectedId={selectedId} />
      </Panel>
    </PageContainer>
  );
}

/** Common metric builders. */
export const countAll = (e: UrbanEvent[]) => e.length;
export const countCritical = (e: UrbanEvent[]) =>
  e.filter((x) => x.severity === 'critical').length;
export const countNew = (e: UrbanEvent[]) =>
  e.filter((x) => Date.now() - new Date(x.timestamp).getTime() < 30 * 60_000).length;
export const countResolved = (e: UrbanEvent[]) =>
  e.filter((x) => x.status === 'resolved').length;
