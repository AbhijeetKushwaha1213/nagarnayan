import type {
  EventCategory,
  EventStatus,
  EventType,
  Severity,
  TrafficLevel,
} from '@/types/domain';

/** Human labels + category grouping for every detectable event type. */
export const EVENT_TYPE_META: Record<
  EventType,
  { label: string; category: EventCategory }
> = {
  POTHOLE: { label: 'Pothole', category: 'road' },
  ROAD_CRACK: { label: 'Road Crack', category: 'road' },
  SURFACE_DAMAGE: { label: 'Surface Damage', category: 'road' },
  ROAD_OBSTRUCTION: { label: 'Road Obstruction', category: 'road' },
  WATERLOGGING: { label: 'Waterlogging', category: 'waterlogging' },
  TRAFFIC_CONGESTION: { label: 'Traffic Congestion', category: 'traffic' },
  TRAFFIC_BOTTLENECK: { label: 'Traffic Bottleneck', category: 'traffic' },
  MISSING_ZEBRA_CROSSING: {
    label: 'Missing Zebra Crossing',
    category: 'infrastructure',
  },
  DAMAGED_SIGN: { label: 'Damaged Traffic Sign', category: 'infrastructure' },
  MISSING_SIGN: { label: 'Missing Traffic Sign', category: 'infrastructure' },
  DAMAGED_DIVIDER: { label: 'Damaged Divider', category: 'infrastructure' },
  MISSING_DIVIDER: { label: 'Missing Divider', category: 'infrastructure' },
  DANGEROUS_CROSSING: { label: 'Dangerous Crossing', category: 'safety' },
  VULNERABLE_PEDESTRIAN: {
    label: 'Vulnerable Pedestrian',
    category: 'safety',
  },
  SCHOOL_ZONE_RISK: { label: 'School Zone Risk', category: 'safety' },
  RASH_DRIVING: { label: 'Rash Driving', category: 'incident' },
  POSSIBLE_INCIDENT: { label: 'Possible Incident', category: 'incident' },
  HIT_AND_RUN: { label: 'Hit & Run', category: 'incident' },
};

export interface CategoryMeta {
  key: EventCategory;
  label: string;
  /** hex used for map markers + accents */
  color: string;
  /** lucide icon name resolved in the UI */
  icon: string;
}

export const CATEGORY_META: Record<EventCategory, CategoryMeta> = {
  incident: { key: 'incident', label: 'Incidents', color: '#dc2626', icon: 'siren' },
  road: { key: 'road', label: 'Road Defects', color: '#ea580c', icon: 'construction' },
  infrastructure: {
    key: 'infrastructure',
    label: 'Infrastructure',
    color: '#d97706',
    icon: 'traffic-cone',
  },
  traffic: { key: 'traffic', label: 'Traffic', color: '#2563eb', icon: 'car-front' },
  safety: { key: 'safety', label: 'Safety', color: '#7c3aed', icon: 'shield-alert' },
  waterlogging: {
    key: 'waterlogging',
    label: 'Waterlogging',
    color: '#0891b2',
    icon: 'waves',
  },
};

export const SEVERITY_META: Record<
  Severity,
  { label: string; color: string; soft: string; rank: number }
> = {
  critical: { label: 'Critical', color: '#dc2626', soft: '#fee2e2', rank: 4 },
  high: { label: 'High', color: '#ea580c', soft: '#ffedd5', rank: 3 },
  medium: { label: 'Medium', color: '#d97706', soft: '#fef3c7', rank: 2 },
  low: { label: 'Low', color: '#2563eb', soft: '#dbeafe', rank: 1 },
};

export const STATUS_META: Record<
  EventStatus,
  { label: string; color: string; soft: string }
> = {
  pending: { label: 'Pending Review', color: '#d97706', soft: '#fef3c7' },
  in_review: { label: 'In Review', color: '#2563eb', soft: '#dbeafe' },
  dispatched: { label: 'Crew Dispatched', color: '#7c3aed', soft: '#ede9fe' },
  resolved: { label: 'Resolved', color: '#059669', soft: '#d1fae5' },
  dismissed: { label: 'Dismissed', color: '#64748b', soft: '#f1f5f9' },
};

export const TRAFFIC_LEVEL_META: Record<
  TrafficLevel,
  { label: string; color: string }
> = {
  low: { label: 'Low', color: '#059669' },
  medium: { label: 'Medium', color: '#d97706' },
  high: { label: 'High', color: '#ea580c' },
  severe: { label: 'Severe', color: '#dc2626' },
};

export const CAMERA_LABEL: Record<string, string> = {
  FRONT_CAMERA: 'Front Camera',
  REAR_CAMERA: 'Rear Camera',
  LEFT_CAMERA: 'Left Camera',
  RIGHT_CAMERA: 'Right Camera',
  CABIN_CAMERA: 'Cabin Camera',
};
