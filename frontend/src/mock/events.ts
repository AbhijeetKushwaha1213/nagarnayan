import type {
  CameraId,
  EventStatus,
  EventType,
  Severity,
  UrbanEvent,
} from '@/types/domain';
import { EVENT_TYPE_META } from '@/config/taxonomy';
import { PLACES, ROUTE_NAMES, type PlacePreset } from './city';

/** ISO timestamp N minutes before now (recomputed at load so feeds feel live). */
function minutesAgo(mins: number): string {
  return new Date(Date.now() - mins * 60_000).toISOString();
}

interface Seed {
  type: EventType;
  severity: Severity;
  confidence: number;
  place: PlacePreset;
  minsAgo: number;
  bus: string;
  camera: CameraId;
  route: string;
  status: EventStatus;
  note?: string;
}

/** Tiny deterministic jitter so co-located events don't overlap exactly. */
function jitter(base: number, seed: number): number {
  return base + (((seed * 9301 + 49297) % 233280) / 233280 - 0.5) * 0.004;
}

const SEEDS: Seed[] = [
  {
    type: 'POTHOLE',
    severity: 'high',
    confidence: 0.94,
    place: PLACES.mgRoad,
    minsAgo: 2,
    bus: 'NN-042',
    camera: 'FRONT_CAMERA',
    route: 'R-01',
    status: 'pending',
    note: 'Deep pothole in the left lane, ~40cm wide. Recurring detection over 3 passes.',
  },
  {
    type: 'TRAFFIC_CONGESTION',
    severity: 'critical',
    confidence: 0.88,
    place: PLACES.civilLinesJn,
    minsAgo: 5,
    bus: 'NN-017',
    camera: 'FRONT_CAMERA',
    route: 'R-01',
    status: 'in_review',
    note: 'Vehicle density severe across all approaches. Signal cycle likely undersized.',
  },
  {
    type: 'WATERLOGGING',
    severity: 'critical',
    confidence: 0.91,
    place: PLACES.stationRoad,
    minsAgo: 8,
    bus: 'NN-033',
    camera: 'FRONT_CAMERA',
    route: 'R-03',
    status: 'dispatched',
    note: 'Standing water across full carriageway near the underpass. Traffic diverting.',
  },
  {
    type: 'DAMAGED_SIGN',
    severity: 'medium',
    confidence: 0.89,
    place: PLACES.airportRoad,
    minsAgo: 12,
    bus: 'NN-051',
    camera: 'RIGHT_CAMERA',
    route: 'R-03',
    status: 'pending',
  },
  {
    type: 'RASH_DRIVING',
    severity: 'critical',
    confidence: 0.82,
    place: PLACES.rambagh,
    minsAgo: 15,
    bus: 'NN-024',
    camera: 'FRONT_CAMERA',
    route: 'R-02',
    status: 'in_review',
    note: 'Two-wheeler weaving through traffic at high speed. Partial plate captured.',
  },
  {
    type: 'MISSING_ZEBRA_CROSSING',
    severity: 'medium',
    confidence: 0.86,
    place: PLACES.georgetown,
    minsAgo: 22,
    bus: 'NN-008',
    camera: 'FRONT_CAMERA',
    route: 'R-02',
    status: 'pending',
  },
  {
    type: 'ROAD_CRACK',
    severity: 'low',
    confidence: 0.79,
    place: PLACES.katra,
    minsAgo: 28,
    bus: 'NN-039',
    camera: 'FRONT_CAMERA',
    route: 'R-02',
    status: 'pending',
  },
  {
    type: 'DANGEROUS_CROSSING',
    severity: 'high',
    confidence: 0.84,
    place: PLACES.chowk,
    minsAgo: 34,
    bus: 'NN-012',
    camera: 'FRONT_CAMERA',
    route: 'R-04',
    status: 'in_review',
    note: 'Pedestrians crossing mid-block near market; no controlled crossing within 200m.',
  },
  {
    type: 'SURFACE_DAMAGE',
    severity: 'medium',
    confidence: 0.9,
    place: PLACES.zeroRoad,
    minsAgo: 41,
    bus: 'NN-042',
    camera: 'FRONT_CAMERA',
    route: 'R-01',
    status: 'pending',
  },
  {
    type: 'TRAFFIC_BOTTLENECK',
    severity: 'high',
    confidence: 0.83,
    place: PLACES.stationRoad,
    minsAgo: 47,
    bus: 'NN-033',
    camera: 'FRONT_CAMERA',
    route: 'R-03',
    status: 'in_review',
  },
  {
    type: 'MISSING_DIVIDER',
    severity: 'high',
    confidence: 0.87,
    place: PLACES.nainiBridge,
    minsAgo: 55,
    bus: 'NN-024',
    camera: 'LEFT_CAMERA',
    route: 'R-02',
    status: 'pending',
    note: 'Median divider missing over a 60m stretch approaching the bridge.',
  },
  {
    type: 'POTHOLE',
    severity: 'medium',
    confidence: 0.92,
    place: PLACES.teliarganj,
    minsAgo: 63,
    bus: 'NN-051',
    camera: 'FRONT_CAMERA',
    route: 'R-01',
    status: 'dispatched',
  },
  {
    type: 'SCHOOL_ZONE_RISK',
    severity: 'high',
    confidence: 0.8,
    place: PLACES.hashimpur,
    minsAgo: 74,
    bus: 'NN-017',
    camera: 'FRONT_CAMERA',
    route: 'R-01',
    status: 'pending',
    note: 'Children near carriageway during dismissal; no speed calming present.',
  },
  {
    type: 'ROAD_OBSTRUCTION',
    severity: 'medium',
    confidence: 0.85,
    place: PLACES.alopibagh,
    minsAgo: 88,
    bus: 'NN-039',
    camera: 'FRONT_CAMERA',
    route: 'R-02',
    status: 'pending',
  },
  {
    type: 'POSSIBLE_INCIDENT',
    severity: 'critical',
    confidence: 0.78,
    place: PLACES.sangam,
    minsAgo: 96,
    bus: 'NN-012',
    camera: 'FRONT_CAMERA',
    route: 'R-04',
    status: 'in_review',
    note: 'Two-vehicle interaction with sudden stop; flagged for operator review.',
  },
  {
    type: 'DAMAGED_DIVIDER',
    severity: 'low',
    confidence: 0.81,
    place: PLACES.rambagh,
    minsAgo: 120,
    bus: 'NN-024',
    camera: 'RIGHT_CAMERA',
    route: 'R-02',
    status: 'resolved',
  },
  {
    type: 'MISSING_SIGN',
    severity: 'medium',
    confidence: 0.83,
    place: PLACES.georgetown,
    minsAgo: 145,
    bus: 'NN-008',
    camera: 'FRONT_CAMERA',
    route: 'R-02',
    status: 'pending',
  },
  {
    type: 'WATERLOGGING',
    severity: 'high',
    confidence: 0.88,
    place: PLACES.chowk,
    minsAgo: 175,
    bus: 'NN-012',
    camera: 'FRONT_CAMERA',
    route: 'R-04',
    status: 'resolved',
  },
  {
    type: 'POTHOLE',
    severity: 'low',
    confidence: 0.76,
    place: PLACES.katra,
    minsAgo: 210,
    bus: 'NN-039',
    camera: 'FRONT_CAMERA',
    route: 'R-02',
    status: 'resolved',
  },
  {
    type: 'HIT_AND_RUN',
    severity: 'critical',
    confidence: 0.72,
    place: PLACES.zeroRoad,
    minsAgo: 265,
    bus: 'NN-042',
    camera: 'FRONT_CAMERA',
    route: 'R-01',
    status: 'dispatched',
    note: 'Suspected hit-and-run; offending vehicle partial plate + colour captured for investigation.',
  },
];

export const MOCK_EVENTS: UrbanEvent[] = SEEDS.map((s, i) => {
  const meta = EVENT_TYPE_META[s.type];
  return {
    id: `EVT-${String(1000 + i)}`,
    type: s.type,
    category: meta.category,
    severity: s.severity,
    confidence: s.confidence,
    title: meta.label,
    location: {
      latitude: jitter(s.place.lat, i + 1),
      longitude: jitter(s.place.lng, i + 7),
      address: s.place.address,
      zone: s.place.zone,
    },
    timestamp: minutesAgo(s.minsAgo),
    source: {
      busId: s.bus,
      busLabel: `Bus ${s.bus}`,
      cameraId: s.camera,
      routeId: s.route,
    },
    status: s.status,
    note: s.note,
    evidenceUrl: undefined,
  } satisfies UrbanEvent;
});

export const ROUTE_NAME_LOOKUP = ROUTE_NAMES;
