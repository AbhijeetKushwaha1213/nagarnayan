/**
 * Nagar Nayan — Pure KPI Computation Utilities
 *
 * Encapsulates calculation of municipal operational KPIs from strict backend schemas.
 */

import type { Alert, Bus, Camera, Stream, UrbanEvent } from '@/types/backend';

export interface DashboardKPISummary {
  activeEventsCount: number;
  criticalHighAlertsCount: number;
  totalBusesCount: number;
  activeBusesCount: number;
  totalCamerasCount: number;
  activeCamerasCount: number;
  totalStreamsCount: number;
  activeStreamsCount: number;
}

export function computeDashboardMetrics(params: {
  events: UrbanEvent[];
  alerts: Alert[];
  buses: Bus[];
  cameras: Camera[];
  streams: Stream[];
}): DashboardKPISummary {
  const { events, alerts, buses, cameras, streams } = params;

  // Active events: all non-terminal events (excluding RESOLVED and REJECTED)
  const activeEventsCount = events.filter(
    (e) => e.status !== 'RESOLVED' && e.status !== 'REJECTED',
  ).length;

  // Critical/High alerts requiring immediate municipal intervention
  const criticalHighAlerts = alerts.filter(
    (a) =>
      (a.severity === 'CRITICAL' || a.severity === 'HIGH') &&
      a.status !== 'RESOLVED' &&
      a.status !== 'DISMISSED',
  );

  return {
    activeEventsCount,
    criticalHighAlertsCount: criticalHighAlerts.length,
    totalBusesCount: buses.length,
    activeBusesCount: buses.filter((b) => b.status === 'active').length,
    totalCamerasCount: cameras.length,
    activeCamerasCount: cameras.filter((c) => c.status === 'active').length,
    totalStreamsCount: streams.length,
    activeStreamsCount: streams.filter((s) => s.status === 'active').length,
  };
}
