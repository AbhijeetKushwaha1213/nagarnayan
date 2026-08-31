import type {
  CongestionHotspot,
  TrafficPoint,
  TrendPoint,
  VehicleClassBreakdown,
} from '@/types/domain';
import { PLACES } from './city';

/** Traffic density across the operating day (0..100 index). */
export const TRAFFIC_TODAY: TrafficPoint[] = [
  { time: '06:00', density: 18 },
  { time: '07:00', density: 34 },
  { time: '08:00', density: 62 },
  { time: '09:00', density: 81 },
  { time: '10:00', density: 68 },
  { time: '11:00', density: 55 },
  { time: '12:00', density: 60 },
  { time: '13:00', density: 64 },
  { time: '14:00', density: 52 },
  { time: '15:00', density: 58 },
  { time: '16:00', density: 71 },
  { time: '17:00', density: 88 },
  { time: '18:00', density: 94 },
  { time: '19:00', density: 79 },
  { time: '20:00', density: 51 },
];

export const VEHICLE_MIX: VehicleClassBreakdown = {
  cars: 4120,
  motorcycles: 6890,
  buses: 540,
  trucks: 980,
};

export const CONGESTION_HOTSPOTS: CongestionHotspot[] = [
  {
    rank: 1,
    location: 'Civil Lines Junction',
    zone: 'Civil Lines',
    level: 'severe',
    avgDelayMin: 14,
    vehicleDensity: 92,
    latitude: PLACES.civilLinesJn.lat,
    longitude: PLACES.civilLinesJn.lng,
  },
  {
    rank: 2,
    location: 'MG Marg Intersection',
    zone: 'Civil Lines',
    level: 'high',
    avgDelayMin: 9,
    vehicleDensity: 78,
    latitude: PLACES.mgRoad.lat,
    longitude: PLACES.mgRoad.lng,
  },
  {
    rank: 3,
    location: 'Railway Station Road',
    zone: 'Civil Lines',
    level: 'high',
    avgDelayMin: 8,
    vehicleDensity: 74,
    latitude: PLACES.stationRoad.lat,
    longitude: PLACES.stationRoad.lng,
  },
  {
    rank: 4,
    location: 'Rambagh Crossing',
    zone: 'Rambagh',
    level: 'medium',
    avgDelayMin: 5,
    vehicleDensity: 61,
    latitude: PLACES.rambagh.lat,
    longitude: PLACES.rambagh.lng,
  },
  {
    rank: 5,
    location: 'Chowk Bazaar Road',
    zone: 'Chowk',
    level: 'medium',
    avgDelayMin: 4,
    vehicleDensity: 57,
    latitude: PLACES.chowk.lat,
    longitude: PLACES.chowk.lng,
  },
];

/** 14-day event trend used by the Analytics module. */
export const EVENT_TRENDS: TrendPoint[] = Array.from({ length: 14 }).map((_, i) => {
  const d = new Date(Date.now() - (13 - i) * 86_400_000);
  const date = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  const wave = Math.sin(i / 2);
  return {
    date,
    potholes: Math.round(12 + wave * 5 + (i % 3)),
    traffic: Math.round(28 + Math.cos(i / 2) * 8 + (i % 4)),
    infrastructure: Math.round(6 + Math.abs(wave) * 4),
    safety: Math.round(4 + ((i * 7) % 5)),
  } satisfies TrendPoint;
});
