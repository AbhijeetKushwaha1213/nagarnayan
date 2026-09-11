/**
 * Nagar Nayan — Urban Events Management
 *
 * Displays validated municipal events from GET /api/v1/events with
 * real-time WebSocket updates, multi-attribute filtering, and coordinate verification.
 */

import { useEffect, useState, useMemo } from 'react';
import { api } from '@/services/apiClient';
import { useRealtime } from '@/context/RealtimeContext';
import { Panel, PanelHeader } from '@/components/ui/Panel';
import { Skeleton } from '@/components/ui/Skeleton';
import { PageContainer } from '@/components/layout/Page';
import { getIcon } from '@/components/ui/icons';
import { filterEvents } from '@/utils/filterUtils';
import type { EventSeverity, EventStatus, UrbanEvent } from '@/types/backend';

const SEVERITY_OPTIONS: ('ALL' | EventSeverity)[] = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
const STATUS_OPTIONS: ('ALL' | EventStatus)[] = [
  'ALL',
  'DETECTED',
  'VERIFIED',
  'OPEN',
  'ACKNOWLEDGED',
  'IN_PROGRESS',
  'RESOLVED',
  'REJECTED',
];

const STANDARD_EVENT_TYPES = [
  'POTHOLE',
  'DAMAGED_ROAD',
  'WATERLOGGING',
  'MISSING_DIVIDER',
  'MISSING_ZEBRA_CROSSING',
  'MISSING_SIGNBOARD',
  'TRAFFIC_CONGESTION',
  'VEHICLE',
  'PEDESTRIAN',
  'OTHER',
];

export function EventsPage() {
  const { events: realtimeEvents } = useRealtime();

  const [events, setEvents] = useState<UrbanEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedSeverity, setSelectedSeverity] = useState<'ALL' | EventSeverity>('ALL');
  const [selectedStatus, setSelectedStatus] = useState<'ALL' | EventStatus>('ALL');
  const [selectedType, setSelectedType] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  const fetchEvents = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getEvents({
        severity: selectedSeverity === 'ALL' ? undefined : selectedSeverity,
        status: selectedStatus === 'ALL' ? undefined : selectedStatus,
        event_type: selectedType === 'ALL' ? undefined : selectedType,
        limit: 150,
      });
      setEvents(data);
    } catch (err: any) {
      setError(err.message || 'Failed to retrieve urban events');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
  }, [selectedSeverity, selectedStatus, selectedType]);

  // Combine REST events with real-time updates safely using ID identity
  const mergedEvents = useMemo(() => {
    const map = new Map<string, UrbanEvent>();
    for (const e of events) map.set(e.id, e);
    for (const e of realtimeEvents) map.set(e.id, e);
    return Array.from(map.values());
  }, [events, realtimeEvents]);

  // Apply deterministic pure filtering logic
  const displayEvents = useMemo(() => {
    return filterEvents(mergedEvents, {
      severity: selectedSeverity,
      status: selectedStatus,
      type: selectedType,
      searchQuery,
    });
  }, [mergedEvents, selectedSeverity, selectedStatus, selectedType, searchQuery]);

  // Unique event types available from data merged with standard catalog
  const uniqueEventTypes = useMemo(() => {
    const types = new Set<string>(STANDARD_EVENT_TYPES);
    for (const e of events) types.add(e.event_type);
    for (const e of realtimeEvents) types.add(e.event_type);
    return Array.from(types).sort();
  }, [events, realtimeEvents]);

  const FilterIcon = getIcon('filter');
  const SearchIcon = getIcon('search');

  return (
    <PageContainer className="flex flex-col gap-4">
      <Panel className="p-4">
        <PanelHeader
          title="Urban Events Registry"
          subtitle="Validated physical road hazards and traffic events correlated from sensor detections"
          icon={<FilterIcon size={16} />}
        />

        {/* Filters Toolbar */}
        <div className="mt-4 flex flex-wrap items-center gap-3 border-b border-border-subtle pb-4">
          {/* Search Input */}
          <div className="relative min-w-[220px] flex-1">
            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-400">
              <SearchIcon size={13} />
            </span>
            <input
              type="text"
              placeholder="Search by event type, ID, or bus..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded border border-border-subtle bg-surface py-1 pl-8 pr-3 text-[12px] text-ink-900 placeholder:text-ink-400 focus:border-brand-500 focus:outline-none"
            />
          </div>

          {/* Event Type Filter */}
          <div className="flex items-center gap-1.5 text-[12px] text-ink-600">
            <span>Type:</span>
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="rounded border border-border-subtle bg-surface px-2 py-1 text-[12px] text-ink-800 focus:outline-none"
            >
              <option value="ALL">All Types</option>
              {uniqueEventTypes.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          {/* Severity Filter */}
          <div className="flex items-center gap-1.5 text-[12px] text-ink-600">
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

          {/* Status Filter */}
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

          {/* Refresh Button */}
          <button
            type="button"
            onClick={fetchEvents}
            className="rounded border border-border-subtle bg-surface px-3 py-1 text-[12px] font-medium text-ink-700 hover:bg-surface-muted"
          >
            Refresh
          </button>
        </div>

        {/* Error Notification */}
        {error ? (
          <div className="mt-4 flex items-center justify-between rounded bg-critical-soft p-3 text-[12px] text-critical">
            <span>{error}</span>
            <button
              type="button"
              onClick={fetchEvents}
              className="font-semibold underline hover:no-underline"
            >
              Try Again
            </button>
          </div>
        ) : null}

        {/* Events Table */}
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-[12px]">
            <thead>
              <tr className="border-b border-border-subtle text-[11px] font-semibold uppercase tracking-wider text-ink-400">
                <th className="pb-2.5">Event Type</th>
                <th className="pb-2.5">Severity</th>
                <th className="pb-2.5">Status</th>
                <th className="pb-2.5">Confidence</th>
                <th className="pb-2.5">Location Availability</th>
                <th className="pb-2.5">First Detected</th>
                <th className="pb-2.5">Last Detected</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle text-ink-700">
              {isLoading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i} className="py-3">
                    <td className="py-3"><Skeleton className="h-4 w-28" /></td>
                    <td className="py-3"><Skeleton className="h-4 w-16" /></td>
                    <td className="py-3"><Skeleton className="h-4 w-20" /></td>
                    <td className="py-3"><Skeleton className="h-4 w-16" /></td>
                    <td className="py-3"><Skeleton className="h-4 w-36" /></td>
                    <td className="py-3"><Skeleton className="h-4 w-24" /></td>
                    <td className="py-3"><Skeleton className="h-4 w-24" /></td>
                  </tr>
                ))
              ) : displayEvents.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-ink-400">
                    <div className="flex flex-col items-center justify-center">
                      <span className="text-[13px] font-medium text-ink-600">No Events Found</span>
                      <span className="text-[11px] text-ink-400 mt-1">
                        No events match the selected criteria or none have been ingested yet.
                      </span>
                    </div>
                  </td>
                </tr>
              ) : (
                displayEvents.map((e) => {
                  const hasCoordinates =
                    e.latitude !== null &&
                    e.longitude !== null &&
                    typeof e.latitude === 'number' &&
                    typeof e.longitude === 'number';

                  return (
                    <tr key={e.id} className="hover:bg-surface-muted transition-colors">
                      <td className="py-3 font-semibold text-ink-900">
                        {e.event_type}
                      </td>
                      <td className="py-3">
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                            e.severity === 'CRITICAL'
                              ? 'bg-rose-100 text-rose-700'
                              : e.severity === 'HIGH'
                              ? 'bg-orange-100 text-orange-700'
                              : e.severity === 'MEDIUM'
                              ? 'bg-yellow-100 text-yellow-800'
                              : 'bg-blue-100 text-blue-700'
                          }`}
                        >
                          {e.severity}
                        </span>
                      </td>
                      <td className="py-3">
                        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-700">
                          {e.status}
                        </span>
                      </td>
                      <td className="py-3">
                        <div className="flex items-center gap-1.5">
                          <div className="h-1.5 w-12 rounded-full bg-slate-200 overflow-hidden">
                            <div
                              className="h-full bg-brand-500 rounded-full"
                              style={{ width: `${Math.min(e.confidence * 100, 100)}%` }}
                            />
                          </div>
                          <span className="text-[11px] text-ink-500 font-mono">
                            {(e.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                      </td>
                      <td className="py-3">
                        {hasCoordinates ? (
                          <div className="flex items-center gap-1 text-emerald-700 font-mono text-[11px]">
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                            <span>
                              {e.latitude!.toFixed(4)}, {e.longitude!.toFixed(4)}
                            </span>
                          </div>
                        ) : (
                          <div className="flex items-center gap-1 text-slate-400 text-[11px]">
                            <span className="h-1.5 w-1.5 rounded-full bg-slate-300" />
                            <span>No GPS Telemetry</span>
                          </div>
                        )}
                      </td>
                      <td className="py-3 text-[11px] text-ink-500 font-mono">
                        {new Date(e.first_detected_at).toLocaleString()}
                      </td>
                      <td className="py-3 text-[11px] text-ink-500 font-mono">
                        {new Date(e.last_detected_at).toLocaleString()}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </Panel>
    </PageContainer>
  );
}
