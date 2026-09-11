/**
 * Nagar Nayan — Operational Command Dashboard
 *
 * Real API-driven dashboard displaying municipal infrastructure counts,
 * active urban events, critical alerts, and live GIS event map.
 */

import { useEffect, useState, useMemo } from 'react';
import { api } from '@/services/apiClient';
import { useRealtime } from '@/context/RealtimeContext';
import { EventGeoJsonMap } from '@/components/map/EventGeoJsonMap';
import { Panel, PanelHeader } from '@/components/ui/Panel';
import { Skeleton } from '@/components/ui/Skeleton';
import { PageContainer } from '@/components/layout/Page';
import { getIcon } from '@/components/ui/icons';
import type {
  Alert,
  Bus,
  Camera,
  GeoJSONFeatureCollection,
  Stream,
  UrbanEvent,
} from '@/types/backend';

interface DashboardStats {
  buses: Bus[];
  cameras: Camera[];
  streams: Stream[];
  events: UrbanEvent[];
  alerts: Alert[];
  geoJson: GeoJSONFeatureCollection | null;
}

export function Dashboard() {
  const { events: realtimeEvents, alerts: realtimeAlerts } = useRealtime();

  const [stats, setStats] = useState<DashboardStats>({
    buses: [],
    cameras: [],
    streams: [],
    events: [],
    alerts: [],
    geoJson: null,
  });

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | undefined>();

  // Initial load via REST API
  const fetchDashboardData = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [eventsRes, alertsRes, busesRes, camerasRes, streamsRes, geoJsonRes] =
        await Promise.allSettled([
          api.getEvents({ limit: 100 }),
          api.getAlerts({ limit: 100 }),
          api.getBuses(),
          api.getCameras(),
          api.getStreams(),
          api.getEventGeoJSON({ limit: 200 }),
        ]);

      setStats({
        events: eventsRes.status === 'fulfilled' ? eventsRes.value : [],
        alerts: alertsRes.status === 'fulfilled' ? alertsRes.value : [],
        buses: busesRes.status === 'fulfilled' ? busesRes.value : [],
        cameras: camerasRes.status === 'fulfilled' ? camerasRes.value : [],
        streams: streamsRes.status === 'fulfilled' ? streamsRes.value : [],
        geoJson: geoJsonRes.status === 'fulfilled' ? geoJsonRes.value : null,
      });

      // Check if critical endpoints failed
      if (eventsRes.status === 'rejected' && busesRes.status === 'rejected') {
        setError('Backend services currently unavailable. Ensure backend server is running on :8080.');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load operational data');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  // Merge REST initial state with realtime WebSocket updates using stable identity
  const mergedEvents = useMemo(() => {
    if (realtimeEvents.length === 0) return stats.events;
    const map = new Map<string, UrbanEvent>();
    // Add REST events
    for (const e of stats.events) map.set(e.id, e);
    // Overlay real-time updates
    for (const e of realtimeEvents) map.set(e.id, e);
    return Array.from(map.values());
  }, [stats.events, realtimeEvents]);

  const mergedAlerts = useMemo(() => {
    if (realtimeAlerts.length === 0) return stats.alerts;
    const map = new Map<string, Alert>();
    // Add REST alerts
    for (const a of stats.alerts) map.set(a.id, a);
    // Overlay real-time updates
    for (const a of realtimeAlerts) map.set(a.id, a);
    return Array.from(map.values());
  }, [stats.alerts, realtimeAlerts]);

  // Derived metrics
  const activeEventsCount = mergedEvents.filter(
    (e) => e.status !== 'RESOLVED' && e.status !== 'REJECTED',
  ).length;

  const criticalHighAlerts = mergedAlerts.filter(
    (a) => (a.severity === 'CRITICAL' || a.severity === 'HIGH') && a.status !== 'RESOLVED' && a.status !== 'DISMISSED',
  );

  const activeBusesCount = stats.buses.filter((b) => b.status === 'active').length;
  const activeCamerasCount = stats.cameras.filter((c) => c.status === 'active').length;
  const activeStreamsCount = stats.streams.filter((s) => s.status === 'active').length;

  const AlertIcon = getIcon('alert-triangle');
  const BellIcon = getIcon('bell');
  const BusIcon = getIcon('bus');
  const VideoIcon = getIcon('video');
  const SignalIcon = getIcon('signal');

  return (
    <PageContainer className="flex flex-col gap-4">
      {/* Error alert banner if any service failed */}
      {error ? (
        <div className="flex items-center justify-between rounded-md border border-critical/20 bg-critical-soft px-4 py-2.5 text-[12px] text-critical">
          <span>{error}</span>
          <button
            type="button"
            onClick={fetchDashboardData}
            className="rounded bg-white/80 px-2 py-1 font-semibold text-critical hover:bg-white"
          >
            Retry Connection
          </button>
        </div>
      ) : null}

      {/* KPI Cards Row */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        {/* Active Events Card */}
        <div className="flex flex-col justify-between rounded-md border border-border-subtle bg-surface p-3.5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium uppercase tracking-wider text-ink-500">
              Active Events
            </span>
            <span className="grid h-7 w-7 place-items-center rounded bg-amber-50 text-amber-600">
              <AlertIcon size={15} />
            </span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            {isLoading ? (
              <Skeleton className="h-7 w-16" />
            ) : (
              <span className="text-[22px] font-bold text-ink-900">{activeEventsCount}</span>
            )}
            <span className="text-[11px] text-ink-400">unresolved</span>
          </div>
        </div>

        {/* Priority Alerts Card */}
        <div className="flex flex-col justify-between rounded-md border border-border-subtle bg-surface p-3.5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium uppercase tracking-wider text-ink-500">
              Critical Alerts
            </span>
            <span className="grid h-7 w-7 place-items-center rounded bg-rose-50 text-rose-600">
              <BellIcon size={15} />
            </span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            {isLoading ? (
              <Skeleton className="h-7 w-16" />
            ) : (
              <span className="text-[22px] font-bold text-rose-600">
                {criticalHighAlerts.length}
              </span>
            )}
            <span className="text-[11px] text-ink-400">High / Critical</span>
          </div>
        </div>

        {/* Bus Fleet Card */}
        <div className="flex flex-col justify-between rounded-md border border-border-subtle bg-surface p-3.5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium uppercase tracking-wider text-ink-500">
              Buses
            </span>
            <span className="grid h-7 w-7 place-items-center rounded bg-blue-50 text-blue-600">
              <BusIcon size={15} />
            </span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            {isLoading ? (
              <Skeleton className="h-7 w-16" />
            ) : (
              <span className="text-[22px] font-bold text-ink-900">{stats.buses.length}</span>
            )}
            <span className="text-[11px] text-ink-400">
              {activeBusesCount} active
            </span>
          </div>
        </div>

        {/* Cameras Card */}
        <div className="flex flex-col justify-between rounded-md border border-border-subtle bg-surface p-3.5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium uppercase tracking-wider text-ink-500">
              Cameras
            </span>
            <span className="grid h-7 w-7 place-items-center rounded bg-purple-50 text-purple-600">
              <VideoIcon size={15} />
            </span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            {isLoading ? (
              <Skeleton className="h-7 w-16" />
            ) : (
              <span className="text-[22px] font-bold text-ink-900">{stats.cameras.length}</span>
            )}
            <span className="text-[11px] text-ink-400">
              {activeCamerasCount} online
            </span>
          </div>
        </div>

        {/* RTSP Streams Card */}
        <div className="flex flex-col justify-between rounded-md border border-border-subtle bg-surface p-3.5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium uppercase tracking-wider text-ink-500">
              Streams
            </span>
            <span className="grid h-7 w-7 place-items-center rounded bg-emerald-50 text-emerald-600">
              <SignalIcon size={15} />
            </span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            {isLoading ? (
              <Skeleton className="h-7 w-16" />
            ) : (
              <span className="text-[22px] font-bold text-ink-900">{stats.streams.length}</span>
            )}
            <span className="text-[11px] text-ink-400">
              {activeStreamsCount} active
            </span>
          </div>
        </div>
      </div>

      {/* Main Content Grid: GIS Map + Priority Feed */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {/* Left: GIS Map Panel */}
        <Panel className="flex flex-col p-4 xl:col-span-2">
          <PanelHeader
            title="Real-Time GIS Municipal Map"
            subtitle="Live spatial projection of validated urban events from bus-camera sensing"
          />
          <div className="mt-2 flex-1">
            <EventGeoJsonMap
              geoJson={stats.geoJson}
              isLoading={isLoading}
              selectedEventId={selectedEventId}
              onSelectEvent={setSelectedEventId}
              className="h-[520px] w-full"
            />
          </div>
        </Panel>

        {/* Right: Active Priority Alerts & Events Feed */}
        <Panel className="flex flex-col p-4">
          <PanelHeader
            title="Active Operational Queue"
            subtitle={`${criticalHighAlerts.length} high priority alerts requiring response`}
          />
          <div className="mt-2 flex-1 overflow-y-auto divide-y divide-border-subtle max-h-[520px]">
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="py-2.5">
                  <Skeleton className="h-4 w-3/4 mb-1.5" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              ))
            ) : criticalHighAlerts.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center text-ink-400">
                <span className="text-[13px] font-medium text-ink-600">No Critical Alerts Pending</span>
                <span className="text-[11px] text-ink-400 mt-1">All urban infrastructure hazards within normal tolerance.</span>
              </div>
            ) : (
              criticalHighAlerts.slice(0, 10).map((alert) => (
                <div
                  key={alert.id}
                  onClick={() => setSelectedEventId(alert.event_id)}
                  className={`cursor-pointer py-3 transition-colors hover:bg-surface-muted px-2 rounded ${
                    selectedEventId === alert.event_id ? 'bg-brand-50/60' : ''
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[12px] font-semibold text-ink-900">{alert.title}</span>
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                        alert.severity === 'CRITICAL'
                          ? 'bg-rose-100 text-rose-700'
                          : 'bg-orange-100 text-orange-700'
                      }`}
                    >
                      {alert.severity}
                    </span>
                  </div>
                  <p className="mt-0.5 text-[11px] text-ink-600 line-clamp-2">{alert.message}</p>
                  <div className="mt-1.5 flex items-center justify-between text-[10px] text-ink-400">
                    <span>Status: {alert.status}</span>
                    <span>
                      {alert.triggered_at ? new Date(alert.triggered_at).toLocaleTimeString() : 'N/A'}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </Panel>
      </div>
    </PageContainer>
  );
}
