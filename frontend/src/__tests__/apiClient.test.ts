import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { api, ApiError } from '@/services/apiClient';

describe('Centralized API Client', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('getEvents builds correct URL with query parameters and returns typed events', async () => {
    const mockEvents = [
      {
        id: '11111111-1111-1111-1111-111111111111',
        event_type: 'POTHOLE',
        severity: 'HIGH',
        status: 'DETECTED',
        latitude: 12.9716,
        longitude: 77.5946,
        confidence: 0.92,
        first_detected_at: '2026-09-11T12:00:00Z',
        last_detected_at: '2026-09-11T12:05:00Z',
        metadata: {},
        created_at: '2026-09-11T12:00:00Z',
        updated_at: '2026-09-11T12:05:00Z',
      },
    ];

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockEvents,
    } as unknown as Response);

    const result = await api.getEvents({ severity: 'HIGH', status: 'DETECTED' });

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const calledUrl = (global.fetch as any).mock.calls[0][0];
    expect(calledUrl).toContain('/api/v1/events?severity=HIGH&status=DETECTED');
    expect(result).toEqual(mockEvents);
  });

  it('getEventGeoJSON calls /api/v1/events/geojson and returns FeatureCollection', async () => {
    const mockGeoJSON = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [77.5946, 12.9716] },
          properties: {
            event_id: '11111111-1111-1111-1111-111111111111',
            event_type: 'POTHOLE',
            status: 'DETECTED',
            severity: 'HIGH',
            confidence: 0.92,
            detected_at: '2026-09-11T12:05:00Z',
          },
        },
      ],
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockGeoJSON,
    } as unknown as Response);

    const result = await api.getEventGeoJSON();
    const calledUrl = (global.fetch as any).mock.calls[0][0];
    expect(calledUrl).toContain('/api/v1/events/geojson');
    expect(result.type).toBe('FeatureCollection');
    expect(result.features).toHaveLength(1);
  });

  it('getAlerts, getBuses, getCameras, getStreams call their respective endpoints', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
    } as unknown as Response);

    await api.getAlerts({ status: 'ACTIVE' });
    expect((global.fetch as any).mock.calls[0][0]).toContain('/api/v1/alerts?status=ACTIVE');

    await api.getBuses();
    expect((global.fetch as any).mock.calls[1][0]).toContain('/api/v1/buses');

    await api.getCameras();
    expect((global.fetch as any).mock.calls[2][0]).toContain('/api/v1/cameras');

    await api.getStreams();
    expect((global.fetch as any).mock.calls[3][0]).toContain('/api/v1/streams');
  });

  it('throws ApiError with detail message on HTTP 4xx/5xx responses', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Requested urban event not found' }),
    } as unknown as Response);

    await expect(api.getEvents()).rejects.toThrow(ApiError);
    await expect(api.getEvents()).rejects.toMatchObject({
      status: 404,
      message: 'Requested urban event not found',
    });
  });

  it('throws ApiError on network connection failure', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Failed to fetch'));

    await expect(api.getBuses()).rejects.toThrow(ApiError);
    await expect(api.getBuses()).rejects.toMatchObject({
      status: 0,
    });
  });

  it('throws ApiError on malformed JSON response', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => {
        throw new SyntaxError('Unexpected token < in JSON');
      },
    } as unknown as Response);

    await expect(api.getCameras()).rejects.toThrow('Malformed JSON received from backend');
  });
});
