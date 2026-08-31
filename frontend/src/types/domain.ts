/**
 * Nagar Nayan — Core domain model
 *
 * These interfaces describe the structured intelligence that Edge-AI on the
 * buses emits and the central platform consumes. The frontend is built against
 * these types so mock data can later be swapped for real API responses without
 * touching the UI layer.
 */

export type EventCategory =
  | 'road'
  | 'traffic'
  | 'infrastructure'
  | 'safety'
  | 'incident'
  | 'waterlogging';

export type EventType =
  // road
  | 'POTHOLE'
  | 'ROAD_CRACK'
  | 'SURFACE_DAMAGE'
  | 'ROAD_OBSTRUCTION'
  // waterlogging
  | 'WATERLOGGING'
  // traffic
  | 'TRAFFIC_CONGESTION'
  | 'TRAFFIC_BOTTLENECK'
  // infrastructure
  | 'MISSING_ZEBRA_CROSSING'
  | 'DAMAGED_SIGN'
  | 'MISSING_SIGN'
  | 'DAMAGED_DIVIDER'
  | 'MISSING_DIVIDER'
  // safety
  | 'DANGEROUS_CROSSING'
  | 'VULNERABLE_PEDESTRIAN'
  | 'SCHOOL_ZONE_RISK'
  // incident
  | 'RASH_DRIVING'
  | 'POSSIBLE_INCIDENT'
  | 'HIT_AND_RUN';

export type Severity = 'critical' | 'high' | 'medium' | 'low';

export type EventStatus =
  | 'pending'
  | 'in_review'
  | 'dispatched'
  | 'resolved'
  | 'dismissed';

export type CameraId =
  | 'FRONT_CAMERA'
  | 'REAR_CAMERA'
  | 'LEFT_CAMERA'
  | 'RIGHT_CAMERA'
  | 'CABIN_CAMERA';

export interface GeoLocation {
  latitude: number;
  longitude: number;
  address: string;
  zone: string;
}

export interface EventSource {
  busId: string;
  busLabel: string;
  cameraId: CameraId;
  routeId: string;
}

export interface UrbanEvent {
  id: string;
  type: EventType;
  category: EventCategory;
  severity: Severity;
  /** model confidence, 0..1 */
  confidence: number;
  location: GeoLocation;
  /** ISO 8601 */
  timestamp: string;
  source: EventSource;
  status: EventStatus;
  /** short human summary used in feeds */
  title: string;
  /** placeholder for the captured evidence frame */
  evidenceUrl?: string;
  note?: string;
}

export type TrafficLevel = 'low' | 'medium' | 'high' | 'severe';

export type BusStatus = 'active' | 'idle' | 'offline' | 'maintenance';

export interface CameraHealth {
  cameraId: CameraId;
  online: boolean;
}

export interface FleetBus {
  id: string;
  label: string;
  routeId: string;
  routeName: string;
  status: BusStatus;
  location: GeoLocation;
  /** heading in degrees, 0 = north */
  heading: number;
  speedKmph: number;
  cameras: CameraHealth[];
  gpsOnline: boolean;
  /** ISO 8601 */
  lastPingAt: string;
  eventsToday: number;
  /** km of road covered so far today */
  coverageKm: number;
}

export interface CongestionHotspot {
  rank: number;
  location: string;
  zone: string;
  level: TrafficLevel;
  avgDelayMin: number;
  vehicleDensity: number;
  latitude: number;
  longitude: number;
}

export interface VehicleClassBreakdown {
  cars: number;
  motorcycles: number;
  buses: number;
  trucks: number;
}

export interface TrafficPoint {
  /** label like "09:00" */
  time: string;
  density: number;
}

export interface TrendPoint {
  date: string;
  potholes: number;
  traffic: number;
  infrastructure: number;
  safety: number;
}

export interface CommandMetrics {
  activeBuses: number;
  totalBuses: number;
  activeEvents: number;
  criticalAlerts: number;
  roadDefects: number;
  congestionHotspots: number;
  /** 0..100 */
  fleetCoveragePct: number;
  cityTrafficLevel: TrafficLevel;
}
