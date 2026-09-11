/**
 * Nagar Nayan — Strict Backend Contracts
 *
 * Types in this file mirror the FastAPI backend Pydantic models.
 * Do not add frontend-only synthetic fields here.
 */

// ── Enums ───────────────────────────────────────────────────────────────────

export type EventSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type EventStatus =
  | 'DETECTED'
  | 'VERIFIED'
  | 'IN_PROGRESS'
  | 'RESOLVED'
  | 'REJECTED';

export type EventType =
  | 'POTHOLE'
  | 'ROAD_CRACK'
  | 'SURFACE_DAMAGE'
  | 'ROAD_OBSTRUCTION'
  | 'WATERLOGGING'
  | 'TRAFFIC_CONGESTION'
  | 'TRAFFIC_BOTTLENECK'
  | 'MISSING_ZEBRA_CROSSING'
  | 'DAMAGED_SIGN'
  | 'MISSING_SIGN'
  | 'DAMAGED_DIVIDER'
  | 'MISSING_DIVIDER'
  | 'DANGEROUS_CROSSING'
  | 'VULNERABLE_PEDESTRIAN'
  | 'SCHOOL_ZONE_RISK'
  | 'RASH_DRIVING'
  | 'POSSIBLE_INCIDENT'
  | 'HIT_AND_RUN'
  | string;

export type AlertSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type AlertStatus =
  | 'ACTIVE'
  | 'NEW'
  | 'ACKNOWLEDGED'
  | 'RESOLVED'
  | 'DISMISSED';

export type AlertType =
  | 'MUNICIPAL_ISSUE'
  | 'INFRASTRUCTURE_HAZARD'
  | 'TRAFFIC_IMPACT'
  | 'SAFETY_RISK'
  | string;

export type BusStatus = 'active' | 'inactive';

export type CameraStatus = 'active' | 'inactive' | 'error';

export type CameraType = 'front' | 'rear' | 'side' | 'interior';

export type StreamStatus = 'active' | 'inactive' | 'error';

export type StreamProtocol = 'rtsp';

// ── Models ──────────────────────────────────────────────────────────────────

export interface Bus {
  id: string;
  bus_number: string;
  route_id: string | null;
  status: BusStatus;
  created_at: string;
  updated_at: string;
}

export interface Camera {
  id: string;
  bus_id: string;
  camera_type: CameraType;
  status: CameraStatus;
  created_at: string;
  updated_at: string;
}

export interface Stream {
  id: string;
  camera_id: string;
  stream_url: string;
  protocol: StreamProtocol;
  status: StreamStatus;
  started_at: string | null;
  stopped_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Detection {
  id: string;
  detection_id?: string;
  camera_id: string;
  bus_id: string;
  stream_id: string | null;
  detection_type: string;
  confidence: number;
  latitude: number | null;
  longitude: number | null;
  detected_at: string;
  frame_reference: string | null;
  metadata: Record<string, any>;
  event_id: string | null;
  created_at: string;
}

export interface UrbanEvent {
  id: string;
  event_type: EventType;
  severity: EventSeverity;
  status: EventStatus;
  latitude: number | null;
  longitude: number | null;
  confidence: number;
  first_detected_at: string;
  last_detected_at: string;
  verified_at?: string | null;
  resolved_at?: string | null;
  bus_id?: string | null;
  camera_id?: string | null;
  evidence_reference?: string | null;
  metadata: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface EventSummary {
  id: string;
  event_type: EventType;
  severity: EventSeverity;
  status: EventStatus;
  latitude: number | null;
  longitude: number | null;
  confidence: number;
  first_detected_at: string;
  last_detected_at: string;
  metadata: Record<string, any>;
}

export interface Alert {
  id: string;
  event_id: string;
  alert_type: AlertType;
  severity: AlertSeverity;
  status: AlertStatus;
  title: string;
  message: string;
  triggered_at: string | null;
  acknowledged_at: string | null;
  resolved_at: string | null;
  metadata: Record<string, any>;
  event?: EventSummary | null;
  created_at: string;
  updated_at: string;
}

// ── GeoJSON Contracts ───────────────────────────────────────────────────────

export interface GeoJSONGeometryPoint {
  type: 'Point';
  coordinates: [number, number]; // [longitude, latitude]
}

export interface GeoJSONEventProperties {
  event_id: string;
  event_type: EventType;
  status: EventStatus;
  severity: EventSeverity;
  confidence: number;
  detected_at: string;
}

export interface GeoJSONEventFeature {
  type: 'Feature';
  geometry: GeoJSONGeometryPoint | null;
  properties: GeoJSONEventProperties;
}

export interface GeoJSONFeatureCollection {
  type: 'FeatureCollection';
  features: GeoJSONEventFeature[];
}

// ── WebSocket Contracts ─────────────────────────────────────────────────────

export type WebSocketMessageType =
  | 'system.connected'
  | 'system.pong'
  | 'event.created'
  | 'event.updated'
  | 'alert.created'
  | 'alert.updated';

export interface WebSocketEnvelope<T = any> {
  type: WebSocketMessageType;
  timestamp: string;
  data: T;
}

export interface SystemConnectedData {
  status: string;
  active_clients: number;
}

export interface SystemPongData {
  status: string;
}

// ── Query Filters ───────────────────────────────────────────────────────────

export interface EventFilterParams {
  event_type?: string;
  status?: string;
  severity?: string;
  bus_id?: string;
  camera_id?: string;
  from_timestamp?: string;
  to_timestamp?: string;
  limit?: number;
  offset?: number;
}

export interface AlertFilterParams {
  status?: string;
  severity?: string;
  event_id?: string;
  from_timestamp?: string;
  to_timestamp?: string;
  limit?: number;
  offset?: number;
}
