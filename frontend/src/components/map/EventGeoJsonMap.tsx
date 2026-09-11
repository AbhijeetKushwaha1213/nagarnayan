/**
 * Nagar Nayan — Real-time GIS Event Map
 *
 * Consumes RFC 7946 GeoJSON FeatureCollections from GET /api/v1/events/geojson.
 * Safely renders markers ONLY for events with valid coordinates.
 * Never fabricates coordinates for missing GPS events or defaults to arbitrary locations.
 */

import { useEffect, useMemo } from 'react';
import { MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { GeoJSONEventFeature, GeoJSONFeatureCollection } from '@/types/backend';
import { extractValidGeoPoints } from '@/utils/geoUtils';

interface EventGeoJsonMapProps {
  geoJson?: GeoJSONFeatureCollection | null;
  isLoading?: boolean;
  error?: string | null;
  selectedEventId?: string;
  onSelectEvent?: (eventId: string) => void;
  className?: string;
  center?: [number, number];
  zoom?: number;
}

// Neutral default viewport when no geographic telemetry is available
const NEUTRAL_CENTER: [number, number] = [0, 0];
const NEUTRAL_ZOOM = 2;

function getSeverityColor(severity: string): string {
  switch (severity?.toUpperCase()) {
    case 'CRITICAL':
      return '#ef4444'; // Red-500
    case 'HIGH':
      return '#f97316'; // Orange-500
    case 'MEDIUM':
      return '#eab308'; // Yellow-500
    case 'LOW':
    default:
      return '#3b82f6'; // Blue-500
  }
}

function createEventMarkerIcon(severity: string, isSelected: boolean): L.DivIcon {
  const color = getSeverityColor(severity);
  const size = isSelected ? 24 : 18;
  const pulseHtml = isSelected
    ? `<span style="position: absolute; inset: -4px; border-radius: 9999px; background-color: ${color}; opacity: 0.5; animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;"></span>`
    : '';

  const html = `
    <div style="position: relative; width: ${size}px; height: ${size}px; display: flex; align-items: center; justify-content: center;">
      ${pulseHtml}
      <div style="width: ${size}px; height: ${size}px; border-radius: 9999px; background-color: ${color}; border: 2px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.4);"></div>
    </div>
  `;

  return L.divIcon({
    html,
    className: 'custom-event-marker',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

function MapController({
  features,
  selectedId,
}: {
  features: GeoJSONEventFeature[];
  selectedId?: string;
}) {
  const map = useMap();

  // 1. Auto-fit to actual data bounds whenever features change and no event is specifically selected
  useEffect(() => {
    if (!selectedId && features.length > 0) {
      const latLngs: L.LatLngExpression[] = features.map((f) => {
        const [lng, lat] = f.geometry!.coordinates;
        return [lat, lng];
      });
      const bounds = L.latLngBounds(latLngs);
      if (bounds.isValid()) {
        map.fitBounds(bounds, { maxZoom: 15, padding: [40, 40] });
      }
    }
  }, [features, selectedId, map]);

  // 2. Fly to explicitly selected event marker
  useEffect(() => {
    if (selectedId) {
      const selected = features.find((f) => f.properties.event_id === selectedId);
      if (
        selected?.geometry?.type === 'Point' &&
        Array.isArray(selected.geometry.coordinates) &&
        selected.geometry.coordinates.length >= 2
      ) {
        const [lng, lat] = selected.geometry.coordinates;
        map.flyTo([lat, lng], Math.max(map.getZoom(), 15), { duration: 0.8 });
      }
    }
  }, [selectedId, features, map]);

  return null;
}

export function EventGeoJsonMap({
  geoJson,
  isLoading,
  error,
  selectedEventId,
  onSelectEvent,
  className = 'h-[500px] w-full',
  center,
  zoom,
}: EventGeoJsonMapProps) {
  // Filter features with valid GeoJSON point coordinates
  // Strictly validate [longitude, latitude] ordering and omit invalid/missing telemetry
  const validFeatures = useMemo(() => extractValidGeoPoints(geoJson), [geoJson]);

  // Determine initial center: provided prop, or first valid feature, or neutral world
  const initialCenter: [number, number] = useMemo(() => {
    if (center) return center;
    if (validFeatures.length > 0) {
      const [lng, lat] = validFeatures[0].geometry!.coordinates;
      return [lat, lng];
    }
    return NEUTRAL_CENTER;
  }, [center, validFeatures]);

  const initialZoom = zoom ?? (validFeatures.length > 0 ? 13 : NEUTRAL_ZOOM);

  return (
    <div className={`relative overflow-hidden rounded-md border border-border-subtle bg-surface ${className}`}>
      {/* Loading Overlay */}
      {isLoading ? (
        <div className="absolute inset-0 z-[1000] flex items-center justify-center bg-surface/60 backdrop-blur-[1px]">
          <div className="flex items-center gap-2 rounded-sm bg-surface-elevated px-3 py-1.5 text-[12px] font-medium text-ink-700 shadow-md">
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
            Loading GIS Telemetry...
          </div>
        </div>
      ) : null}

      {/* Error Overlay */}
      {error ? (
        <div className="absolute inset-x-3 top-3 z-[1000] flex items-center justify-between rounded bg-critical-soft px-3 py-2 text-[12px] text-critical">
          <span>Failed to load GeoJSON: {error}</span>
        </div>
      ) : null}

      {/* Empty State Banner */}
      {!isLoading && !error && validFeatures.length === 0 ? (
        <div className="absolute bottom-4 left-4 z-[1000] rounded bg-surface/90 px-3 py-1.5 text-[11px] font-medium text-ink-500 shadow-sm backdrop-blur-sm">
          No geo-located events active
        </div>
      ) : null}

      <MapContainer
        center={initialCenter}
        zoom={initialZoom}
        zoomControl
        className="h-full w-full"
        preferCanvas
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
          subdomains="abcd"
          maxZoom={20}
        />

        {validFeatures.map((feature) => {
          const [lng, lat] = feature.geometry!.coordinates;
          const props = feature.properties;
          const isSelected = props.event_id === selectedEventId;

          return (
            <Marker
              key={props.event_id}
              position={[lat, lng]}
              icon={createEventMarkerIcon(props.severity, isSelected)}
              eventHandlers={{
                click: () => onSelectEvent?.(props.event_id),
              }}
              zIndexOffset={props.severity === 'CRITICAL' ? 1000 : 0}
            >
              <Popup>
                <div className="min-w-[190px] text-left">
                  <div className="flex items-center justify-between gap-2 border-b border-border-subtle pb-1">
                    <span className="text-[12px] font-bold text-ink-900">
                      {props.event_type}
                    </span>
                    <span
                      className="rounded px-1.5 py-0.5 text-[10px] font-bold uppercase"
                      style={{
                        backgroundColor: `${getSeverityColor(props.severity)}22`,
                        color: getSeverityColor(props.severity),
                      }}
                    >
                      {props.severity}
                    </span>
                  </div>
                  <div className="mt-1.5 space-y-0.5 text-[11px] text-ink-600">
                    <p>Status: <span className="font-medium text-ink-800">{props.status}</span></p>
                    <p>Confidence: <span className="font-medium text-ink-800">{(props.confidence * 100).toFixed(0)}%</span></p>
                    <p>GPS: <span className="font-mono text-[10px] text-ink-500">{lat.toFixed(5)}, {lng.toFixed(5)}</span></p>
                    <p className="text-[10px] text-ink-400">
                      Detected: {new Date(props.detected_at).toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              </Popup>
            </Marker>
          );
        })}

        <MapController features={validFeatures} selectedId={selectedEventId} />
      </MapContainer>
    </div>
  );
}
