/**
 * Nagar Nayan — Centralized API Client
 *
 * Provides typed, error-handled HTTP requests to the FastAPI backend.
 * Do not scatter direct fetch calls throughout UI components.
 */

import { ENV } from '@/config/env';
import type {
  Alert,
  AlertFilterParams,
  Bus,
  Camera,
  EventFilterParams,
  GeoJSONFeatureCollection,
  Stream,
  UrbanEvent,
} from '@/types/backend';

export class ApiError extends Error {
  public status: number;
  public details?: unknown;

  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

function buildQueryString(params?: Record<string, any>): string {
  if (!params) return '';
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.append(key, String(value));
    }
  }
  const str = searchParams.toString();
  return str ? `?${str}` : '';
}

async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${ENV.API_URL}${endpoint}`;
  const headers = new Headers(options.headers || {});
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }

  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (err: any) {
    throw new ApiError(
      `Network error connecting to backend at ${url}: ${err.message || 'Connection refused'}`,
      0,
      err,
    );
  }

  if (!response.ok) {
    let errorDetail: any = null;
    let message = `API request failed with status ${response.status}`;
    try {
      errorDetail = await response.json();
      if (errorDetail?.detail) {
        message = typeof errorDetail.detail === 'string'
          ? errorDetail.detail
          : JSON.stringify(errorDetail.detail);
      }
    } catch {
      // response wasn't JSON
    }
    throw new ApiError(message, response.status, errorDetail);
  }

  // Handle empty bodies (e.g. 204 No Content)
  if (response.status === 204) {
    return null as T;
  }

  try {
    return await response.json() as T;
  } catch (err: any) {
    throw new ApiError('Malformed JSON received from backend', response.status, err);
  }
}

// ── Exported API Methods ───────────────────────────────────────────────────

export const api = {
  /**
   * Fetch urban events list with optional type, severity, and status filters.
   */
  async getEvents(params?: EventFilterParams): Promise<UrbanEvent[]> {
    const qs = buildQueryString(params);
    return apiRequest<UrbanEvent[]>(`/api/v1/events${qs}`);
  },

  /**
   * Fetch urban events formatted as RFC 7946 GeoJSON FeatureCollection.
   */
  async getEventGeoJSON(params?: EventFilterParams): Promise<GeoJSONFeatureCollection> {
    const qs = buildQueryString(params);
    return apiRequest<GeoJSONFeatureCollection>(`/api/v1/events/geojson${qs}`);
  },

  /**
   * Fetch municipal alerts queue with optional status and severity filters.
   */
  async getAlerts(params?: AlertFilterParams): Promise<Alert[]> {
    const qs = buildQueryString(params);
    return apiRequest<Alert[]>(`/api/v1/alerts${qs}`);
  },

  /**
   * Fetch registered bus fleet units.
   */
  async getBuses(): Promise<Bus[]> {
    return apiRequest<Bus[]>('/api/v1/buses');
  },

  /**
   * Fetch registered camera sensors.
   */
  async getCameras(): Promise<Camera[]> {
    return apiRequest<Camera[]>('/api/v1/cameras');
  },

  /**
   * Fetch registered video stream metadata records.
   */
  async getStreams(): Promise<Stream[]> {
    return apiRequest<Stream[]>('/api/v1/streams');
  },
};
