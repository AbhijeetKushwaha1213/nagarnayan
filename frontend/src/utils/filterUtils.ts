/**
 * Nagar Nayan — Pure Filtering & Sorting Utilities
 *
 * Implements deterministic filtering for Urban Events and Municipal Alerts.
 */

import type {
  Alert,
  AlertSeverity,
  AlertStatus,
  EventSeverity,
  EventStatus,
  UrbanEvent,
} from '@/types/backend';

export interface EventFilterCriteria {
  severity?: 'ALL' | EventSeverity;
  status?: 'ALL' | EventStatus;
  type?: string;
  searchQuery?: string;
}

export function filterEvents(
  events: UrbanEvent[],
  criteria: EventFilterCriteria,
): UrbanEvent[] {
  const { severity = 'ALL', status = 'ALL', type = 'ALL', searchQuery = '' } = criteria;

  return events
    .filter((e) => {
      const matchesSeverity = severity === 'ALL' || e.severity === severity;
      const matchesStatus = status === 'ALL' || e.status === status;
      const matchesType = type === 'ALL' || e.event_type === type;
      return matchesSeverity && matchesStatus && matchesType;
    })
    .filter((e) => {
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      return (
        e.event_type.toLowerCase().includes(q) ||
        e.id.toLowerCase().includes(q) ||
        (e.bus_id && e.bus_id.toLowerCase().includes(q))
      );
    })
    .sort(
      (a, b) => new Date(b.last_detected_at).getTime() - new Date(a.last_detected_at).getTime(),
    );
}

export interface AlertFilterCriteria {
  severity?: 'ALL' | AlertSeverity;
  status?: 'ALL' | AlertStatus;
}

export function filterAlerts(
  alerts: Alert[],
  criteria: AlertFilterCriteria,
): Alert[] {
  const { severity = 'ALL', status = 'ALL' } = criteria;

  return alerts
    .filter((a) => {
      const matchesSeverity = severity === 'ALL' || a.severity === severity;
      const matchesStatus = status === 'ALL' || a.status === status;
      return matchesSeverity && matchesStatus;
    })
    .sort((a, b) => {
      const tA = a.triggered_at ? new Date(a.triggered_at).getTime() : new Date(a.created_at).getTime();
      const tB = b.triggered_at ? new Date(b.triggered_at).getTime() : new Date(b.created_at).getTime();
      return tB - tA;
    });
}
