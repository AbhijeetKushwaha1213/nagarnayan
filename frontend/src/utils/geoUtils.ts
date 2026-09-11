/**
 * Nagar Nayan — GIS Geometry & Telemetry Utilities
 *
 * Validates GeoJSON FeatureCollections and Point geometries strictly.
 * Rejects invalid coordinates and ensures no fabricated coordinates are rendered.
 */

import type { GeoJSONEventFeature, GeoJSONFeatureCollection } from '@/types/backend';

export function extractValidGeoPoints(
  geoJson?: GeoJSONFeatureCollection | null,
): GeoJSONEventFeature[] {
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
