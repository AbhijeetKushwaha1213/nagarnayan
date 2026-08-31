import { useQuery } from '@tanstack/react-query';
import {
  getCommandMetrics,
  getEvent,
  getTraffic,
  getTrends,
  listEvents,
  listFleet,
} from './api';

/**
 * Query hooks. Components consume these — never the raw service — so caching,
 * loading and refetch behaviour stay centralized and backend-swap-ready.
 */

export const queryKeys = {
  events: ['events'] as const,
  event: (id: string) => ['events', id] as const,
  fleet: ['fleet'] as const,
  traffic: ['traffic'] as const,
  trends: ['trends'] as const,
  metrics: ['metrics'] as const,
};

export function useEvents() {
  return useQuery({ queryKey: queryKeys.events, queryFn: listEvents });
}

export function useEvent(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.event(id ?? '_'),
    queryFn: () => getEvent(id as string),
    enabled: Boolean(id),
  });
}

export function useFleet() {
  return useQuery({ queryKey: queryKeys.fleet, queryFn: listFleet });
}

export function useTraffic() {
  return useQuery({ queryKey: queryKeys.traffic, queryFn: getTraffic });
}

export function useTrends() {
  return useQuery({ queryKey: queryKeys.trends, queryFn: getTrends });
}

export function useCommandMetrics() {
  return useQuery({ queryKey: queryKeys.metrics, queryFn: getCommandMetrics });
}
