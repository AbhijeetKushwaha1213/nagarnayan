import { describe, it, expect } from 'vitest';
import type { GeoJSONFeatureCollection } from '@/types/backend';

describe('GIS GeoJSON Parsing & Coordinate Validation', () => {
  // Helper function mimicking the parsing logic of EventGeoJsonMap
  function extractValidPoints(geoJson?: GeoJSONFeatureCollection | null) {
    if (!geoJson?.features || !Array.isArray(geoJson.features)) {
      return [];
    }
    return geoJson.features.filter((f) => {
      if (f.geometry?.type !== 'Point') return false;
      const coords = f.geometry.coordinates;
      if (!Array.isArray(coords) || coords.length < 2) return false;
      const [lng, lat] = coords;
      return (
        typeof lng === 'number' &&
        !isNaN(lng) &&
        typeof lat === 'number' &&
        !isNaN(lat) &&
        lat >= -90 &&
        lat <= 90 &&
        lng >= -180 &&
        lng <= 180
      );
    });
  }

  it('correctly parses features with valid Point coordinates', () => {
    const geoJson: GeoJSONFeatureCollection = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [77.5946, 12.9716] },
          properties: {
            event_id: 'e1',
            event_type: 'POTHOLE',
            status: 'DETECTED',
            severity: 'HIGH',
            confidence: 0.9,
            detected_at: '2026-09-11T12:00:00Z',
          },
        },
      ],
    };

    const valid = extractValidPoints(geoJson);
    expect(valid).toHaveLength(1);
    expect(valid[0].geometry!.coordinates).toEqual([77.5946, 12.9716]);
  });

  it('strictly excludes events with missing coordinates without fabricating fake coordinates', () => {
    const geoJson: GeoJSONFeatureCollection = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: null, // GPS telemetry missing
          properties: {
            event_id: 'e2',
            event_type: 'POTHOLE',
            status: 'DETECTED',
            severity: 'MEDIUM',
            confidence: 0.8,
            detected_at: '2026-09-11T12:00:00Z',
          },
        },
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [77.60, 12.98] },
          properties: {
            event_id: 'e3',
            event_type: 'WATERLOGGING',
            status: 'DETECTED',
            severity: 'CRITICAL',
            confidence: 0.95,
            detected_at: '2026-09-11T12:05:00Z',
          },
        },
      ],
    };

    const valid = extractValidPoints(geoJson);
    expect(valid).toHaveLength(1);
    expect(valid[0].properties.event_id).toBe('e3');
  });

  it('rejects out of bounds coordinates', () => {
    const geoJson: GeoJSONFeatureCollection = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [200.0, 95.0] }, // invalid lat/lng
          properties: {
            event_id: 'e4',
            event_type: 'POTHOLE',
            status: 'DETECTED',
            severity: 'LOW',
            confidence: 0.7,
            detected_at: '2026-09-11T12:00:00Z',
          },
        },
      ],
    };

    const valid = extractValidPoints(geoJson);
    expect(valid).toHaveLength(0);
  });

  it('gracefully handles empty FeatureCollections and null input', () => {
    expect(extractValidPoints(null)).toHaveLength(0);
    expect(extractValidPoints(undefined)).toHaveLength(0);
    expect(extractValidPoints({ type: 'FeatureCollection', features: [] })).toHaveLength(0);
  });
});
