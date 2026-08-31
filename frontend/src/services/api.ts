import type {
  CommandMetrics,
  CongestionHotspot,
  FleetBus,
  TrafficPoint,
  TrendPoint,
  UrbanEvent,
  VehicleClassBreakdown,
} from '@/types/domain';
import { MOCK_EVENTS } from '@/mock/events';
import { MOCK_FLEET } from '@/mock/fleet';
import {
  CONGESTION_HOTSPOTS,
  EVENT_TRENDS,
  TRAFFIC_TODAY,
  VEHICLE_MIX,
} from '@/mock/traffic';

/**
 * Data-access layer.
 *
 * Every function here mirrors a future REST/WebSocket endpoint on the FastAPI
 * backend (see endpoint map below). The UI only ever calls this module, so
 * swapping mock data for `fetch(...)` calls later requires no component changes.
 *
 *   GET /api/events            → listEvents()
 *   GET /api/events/{id}       → getEvent(id)
 *   GET /api/map/events        → listEvents() (filtered client-side today)
 *   GET /api/fleet             → listFleet()
 *   GET /api/traffic           → getTraffic()
 *   GET /api/analytics         → getTrends()
 *   GET /api/summary           → getCommandMetrics()
 */

const LATENCY_MS = 260;

function delay<T>(payload: T, ms = LATENCY_MS): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(payload), ms));
}

function sortByRecency(events: UrbanEvent[]): UrbanEvent[] {
  return [...events].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
  );
}

export function listEvents(): Promise<UrbanEvent[]> {
  return delay(sortByRecency(MOCK_EVENTS));
}

export function getEvent(id: string): Promise<UrbanEvent | undefined> {
  return delay(MOCK_EVENTS.find((e) => e.id === id));
}

export function listFleet(): Promise<FleetBus[]> {
  return delay(MOCK_FLEET);
}

export interface TrafficBundle {
  today: TrafficPoint[];
  vehicleMix: VehicleClassBreakdown;
  hotspots: CongestionHotspot[];
}

export function getTraffic(): Promise<TrafficBundle> {
  return delay({
    today: TRAFFIC_TODAY,
    vehicleMix: VEHICLE_MIX,
    hotspots: CONGESTION_HOTSPOTS,
  });
}

export function getTrends(): Promise<TrendPoint[]> {
  return delay(EVENT_TRENDS);
}

/** Derived operational rollup for the Command Center header + KPI row. */
export function getCommandMetrics(): Promise<CommandMetrics> {
  const activeBuses = MOCK_FLEET.filter((b) => b.status === 'active').length;
  const openEvents = MOCK_EVENTS.filter(
    (e) => e.status !== 'resolved' && e.status !== 'dismissed',
  );
  const critical = openEvents.filter((e) => e.severity === 'critical').length;
  const roadDefects = openEvents.filter(
    (e) => e.category === 'road' || e.category === 'waterlogging',
  ).length;

  return delay({
    activeBuses,
    totalBuses: MOCK_FLEET.length,
    activeEvents: openEvents.length,
    criticalAlerts: critical,
    roadDefects,
    congestionHotspots: CONGESTION_HOTSPOTS.filter(
      (h) => h.level === 'high' || h.level === 'severe',
    ).length,
    fleetCoveragePct: 82,
    cityTrafficLevel: 'high',
  });
}
