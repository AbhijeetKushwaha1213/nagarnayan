import type { CameraId, FleetBus } from '@/types/domain';
import { ROUTE_NAMES, ROUTE_PATHS } from './city';

function pingAgo(mins: number): string {
  return new Date(Date.now() - mins * 60_000).toISOString();
}

const ALL_CAMERAS: CameraId[] = [
  'FRONT_CAMERA',
  'REAR_CAMERA',
  'LEFT_CAMERA',
  'RIGHT_CAMERA',
];

function cams(offline: CameraId[] = []) {
  return ALL_CAMERAS.map((cameraId) => ({
    cameraId,
    online: !offline.includes(cameraId),
  }));
}

/** Place a bus at a vertex along its route path. */
function onRoute(routeId: string, idx: number): [number, number] {
  const path = ROUTE_PATHS[routeId];
  return path[Math.min(idx, path.length - 1)];
}

interface BusSeed {
  id: string;
  route: string;
  status: FleetBus['status'];
  pathIdx: number;
  heading: number;
  speed: number;
  offlineCams?: CameraId[];
  gpsOnline?: boolean;
  pingMins: number;
  eventsToday: number;
  coverageKm: number;
}

const SEEDS: BusSeed[] = [
  { id: 'NN-042', route: 'R-01', status: 'active', pathIdx: 3, heading: 210, speed: 24, pingMins: 0, eventsToday: 14, coverageKm: 62 },
  { id: 'NN-017', route: 'R-01', status: 'active', pathIdx: 2, heading: 195, speed: 12, pingMins: 0, eventsToday: 9, coverageKm: 48 },
  { id: 'NN-051', route: 'R-03', status: 'active', pathIdx: 1, heading: 90, speed: 31, pingMins: 1, eventsToday: 7, coverageKm: 71 },
  { id: 'NN-033', route: 'R-03', status: 'active', pathIdx: 2, heading: 75, speed: 8, pingMins: 0, eventsToday: 11, coverageKm: 55, offlineCams: ['REAR_CAMERA'] },
  { id: 'NN-024', route: 'R-02', status: 'active', pathIdx: 2, heading: 15, speed: 27, pingMins: 0, eventsToday: 12, coverageKm: 66 },
  { id: 'NN-008', route: 'R-02', status: 'active', pathIdx: 3, heading: 20, speed: 19, pingMins: 2, eventsToday: 6, coverageKm: 43 },
  { id: 'NN-012', route: 'R-04', status: 'active', pathIdx: 1, heading: 160, speed: 22, pingMins: 1, eventsToday: 10, coverageKm: 51 },
  { id: 'NN-039', route: 'R-02', status: 'active', pathIdx: 1, heading: 10, speed: 16, pingMins: 3, eventsToday: 8, coverageKm: 39 },
  { id: 'NN-061', route: 'R-04', status: 'idle', pathIdx: 3, heading: 200, speed: 0, pingMins: 6, eventsToday: 4, coverageKm: 22 },
  { id: 'NN-070', route: 'R-01', status: 'maintenance', pathIdx: 5, heading: 0, speed: 0, pingMins: 42, eventsToday: 0, coverageKm: 0, offlineCams: ['FRONT_CAMERA', 'REAR_CAMERA', 'LEFT_CAMERA', 'RIGHT_CAMERA'], gpsOnline: false },
  { id: 'NN-088', route: 'R-03', status: 'offline', pathIdx: 4, heading: 0, speed: 0, pingMins: 118, eventsToday: 3, coverageKm: 18, offlineCams: ['FRONT_CAMERA', 'REAR_CAMERA', 'LEFT_CAMERA', 'RIGHT_CAMERA'], gpsOnline: false },
  { id: 'NN-095', route: 'R-04', status: 'active', pathIdx: 2, heading: 175, speed: 29, pingMins: 0, eventsToday: 5, coverageKm: 47 },
];

export const MOCK_FLEET: FleetBus[] = SEEDS.map((s) => {
  const [lat, lng] = onRoute(s.route, s.pathIdx);
  return {
    id: s.id,
    label: `Bus ${s.id}`,
    routeId: s.route,
    routeName: ROUTE_NAMES[s.route],
    status: s.status,
    location: {
      latitude: lat,
      longitude: lng,
      address: ROUTE_NAMES[s.route],
      zone: '—',
    },
    heading: s.heading,
    speedKmph: s.speed,
    cameras: cams(s.offlineCams),
    gpsOnline: s.gpsOnline ?? true,
    lastPingAt: pingAgo(s.pingMins),
    eventsToday: s.eventsToday,
    coverageKm: s.coverageKm,
  } satisfies FleetBus;
});
