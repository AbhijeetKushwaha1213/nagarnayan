/**
 * Nagar Nayan — Real-time GIS Live Map View
 *
 * Full-page GIS situational map consuming GET /api/v1/events/geojson
 * with interactive feature filtering and spatial telemetry inspection.
 */

import { useEffect, useState, useMemo } from 'react';
import { api } from '@/services/apiClient';
import { EventGeoJsonMap } from '@/components/map/EventGeoJsonMap';
import { Panel, PanelHeader } from '@/components/ui/Panel';
import { PageContainer } from '@/components/layout/Page';
import { getIcon } from '@/components/ui/icons';
import type { EventSeverity, EventStatus, GeoJSONFeatureCollection } from '@/types/backend';

const SEVERITY_OPTIONS: ('ALL' | EventSeverity)[] = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
const STATUS_OPTIONS: ('ALL' | EventStatus)[] = [
  'ALL',
  'DETECTED',
  'VERIFIED',
  'IN_PROGRESS',
  'RESOLVED',
  'REJECTED',
];

export function LiveMap() {
  const [geoJson, setGeoJson] = useState<GeoJSONFeatureCollection | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedSeverity, setSelectedSeverity] = useState<'ALL' | EventSeverity>('ALL');
  const [selectedStatus, setSelectedStatus] = useState<'ALL' | EventStatus>('ALL');
  const [selectedEventId, setSelectedEventId] = useState<string | undefined>();

  const fetchGeoJSON = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getEventGeoJSON({
        severity: selectedSeverity === 'ALL' ? undefined : selectedSeverity,
        status: selectedStatus === 'ALL' ? undefined : selectedStatus,
        limit: 250,
      });
      setGeoJson(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load GeoJSON data');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchGeoJSON();
  }, [selectedSeverity, selectedStatus]);

  const features = useMemo(() => geoJson?.features || [], [geoJson]);

  const selectedFeature = useMemo(
    () => features.find((f) => f.properties.event_id === selectedEventId),
    [features, selectedEventId],
  );

  const MapIcon = getIcon('map');
  const FilterIcon = getIcon('filter');

  return (
    <PageContainer className="flex flex-col gap-4">
      <Panel className="p-4">
        <PanelHeader
          title="Municipal GIS Event Mapping"
          subtitle="Spatial telemetry overlay of validated urban hazards across Bangalore municipal road grid"
          icon={<MapIcon size={16} />}
        />

        {/* Filter Toolbar */}
        <div className="mt-3 flex flex-wrap items-center gap-3 border-b border-border-subtle pb-3">
          <div className="flex items-center gap-1.5 text-[12px] text-ink-600">
            <FilterIcon size={13} />
            <span>Severity:</span>
            <select
              value={selectedSeverity}
              onChange={(e) => setSelectedSeverity(e.target.value as any)}
              className="rounded border border-border-subtle bg-surface px-2 py-1 text-[12px] text-ink-800 focus:outline-none"
            >
              {SEVERITY_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-1.5 text-[12px] text-ink-600">
            <span>Status:</span>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value as any)}
              className="rounded border border-border-subtle bg-surface px-2 py-1 text-[12px] text-ink-800 focus:outline-none"
            >
              {STATUS_OPTIONS.map((st) => (
                <option key={st} value={st}>
                  {st}
                </option>
              ))}
            </select>
          </div>

          <span className="text-[11px] text-ink-400">
            {features.length} feature{features.length === 1 ? '' : 's'} returned
          </span>

          <button
            type="button"
            onClick={fetchGeoJSON}
            className="ml-auto rounded border border-border-subtle bg-surface px-3 py-1 text-[12px] text-ink-700 hover:bg-surface-muted"
          >
            Refresh Map
          </button>
        </div>

        {/* Map and Details Grid */}
        <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-4">
          <div className="xl:col-span-3">
            <EventGeoJsonMap
              geoJson={geoJson}
              isLoading={isLoading}
              error={error}
              selectedEventId={selectedEventId}
              onSelectEvent={setSelectedEventId}
              className="h-[600px] w-full"
            />
          </div>

          {/* Side Feature Details */}
          <div className="flex flex-col gap-3 rounded-md border border-border-subtle bg-surface-muted p-3">
            <h3 className="text-[12px] font-semibold text-ink-900 border-b border-border-subtle pb-2">
              Selected Event Telemetry
            </h3>

            {selectedFeature ? (
              <div className="space-y-2 text-[12px] text-ink-700">
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-bold text-ink-900">
                    {selectedFeature.properties.event_type}
                  </span>
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                      selectedFeature.properties.severity === 'CRITICAL'
                        ? 'bg-rose-100 text-rose-700'
                        : selectedFeature.properties.severity === 'HIGH'
                        ? 'bg-orange-100 text-orange-700'
                        : selectedFeature.properties.severity === 'MEDIUM'
                        ? 'bg-yellow-100 text-yellow-800'
                        : 'bg-blue-100 text-blue-700'
                    }`}
                  >
                    {selectedFeature.properties.severity}
                  </span>
                </div>

                <div className="rounded bg-surface p-2.5 space-y-1 text-[11px] border border-border-subtle">
                  <p>
                    Status: <span className="font-semibold">{selectedFeature.properties.status}</span>
                  </p>
                  <p>
                    Confidence:{' '}
                    <span className="font-semibold font-mono">
                      {(selectedFeature.properties.confidence * 100).toFixed(0)}%
                    </span>
                  </p>
                  <p>
                    Detected At:{' '}
                    <span className="font-mono">
                      {new Date(selectedFeature.properties.detected_at).toLocaleString()}
                    </span>
                  </p>
                  {selectedFeature.geometry ? (
                    <p className="font-mono text-emerald-700">
                      GPS: {selectedFeature.geometry.coordinates[1].toFixed(5)},{' '}
                      {selectedFeature.geometry.coordinates[0].toFixed(5)}
                    </p>
                  ) : (
                    <p className="text-ink-400">Coordinates: Not Available</p>
                  )}
                  <p className="font-mono text-[10px] text-ink-400 truncate">
                    UUID: {selectedFeature.properties.event_id}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => setSelectedEventId(undefined)}
                  className="w-full rounded border border-border-subtle bg-surface py-1 text-[11px] text-ink-600 hover:bg-slate-100"
                >
                  Clear Selection
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-16 text-center text-ink-400">
                <MapIcon size={24} className="mb-2 opacity-50" />
                <p className="text-[12px] font-medium text-ink-600">No Event Selected</p>
                <p className="text-[11px] mt-1 text-ink-400">
                  Click any marker on the map to inspect spatial properties.
                </p>
              </div>
            )}
          </div>
        </div>
      </Panel>
    </PageContainer>
  );
}
