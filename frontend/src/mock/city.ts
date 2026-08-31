import type { EventCategory } from '@/types/domain';

/**
 * Reference city: Prayagraj. All mock geodata is anchored here so the map,
 * fleet routes and events line up on real streets.
 */
export const CITY = {
  name: 'Prayagraj',
  authority: 'City Transport & Urban Operations Authority',
  center: [25.4484, 81.8397] as [number, number],
  defaultZoom: 13,
  bounds: {
    north: 25.51,
    south: 25.4,
    east: 81.9,
    west: 81.78,
  },
};

export interface ZoneDef {
  id: string;
  name: string;
}

export const ZONES: ZoneDef[] = [
  { id: 'Z1', name: 'Civil Lines' },
  { id: 'Z2', name: 'Georgetown' },
  { id: 'Z3', name: 'Katra' },
  { id: 'Z4', name: 'Chowk' },
  { id: 'Z5', name: 'Rambagh' },
  { id: 'Z6', name: 'Naini' },
  { id: 'Z7', name: 'Teliarganj' },
];

/** Named road/junction presets used to place events realistically. */
export interface PlacePreset {
  address: string;
  zone: string;
  lat: number;
  lng: number;
}

export const PLACES: Record<string, PlacePreset> = {
  mgRoad: { address: 'MG Marg', zone: 'Civil Lines', lat: 25.452, lng: 81.829 },
  civilLinesJn: {
    address: 'Civil Lines Junction',
    zone: 'Civil Lines',
    lat: 25.456,
    lng: 81.833,
  },
  stationRoad: {
    address: 'Railway Station Road',
    zone: 'Civil Lines',
    lat: 25.447,
    lng: 81.826,
  },
  airportRoad: { address: 'Airport Road', zone: 'Bamrauli', lat: 25.442, lng: 81.784 },
  zeroRoad: { address: 'Zero Road', zone: 'Chowk', lat: 25.436, lng: 81.846 },
  chowk: { address: 'Chowk Bazaar Road', zone: 'Chowk', lat: 25.43, lng: 81.838 },
  katra: { address: 'Katra Main Road', zone: 'Katra', lat: 25.462, lng: 81.862 },
  georgetown: {
    address: 'Georgetown Road',
    zone: 'Georgetown',
    lat: 25.468,
    lng: 81.848,
  },
  rambagh: { address: 'Rambagh Crossing', zone: 'Rambagh', lat: 25.455, lng: 81.86 },
  nainiBridge: { address: 'Naini Bridge Approach', zone: 'Naini', lat: 25.418, lng: 81.87 },
  teliarganj: {
    address: 'Teliarganj Main Road',
    zone: 'Teliarganj',
    lat: 25.49,
    lng: 81.87,
  },
  alopibagh: { address: 'Alopibagh Road', zone: 'Katra', lat: 25.44, lng: 81.86 },
  sangam: { address: 'Sangam Approach Road', zone: 'Naini', lat: 25.425, lng: 81.884 },
  hashimpur: { address: 'Hashimpur Road', zone: 'Civil Lines', lat: 25.459, lng: 81.823 },
};

export const CATEGORY_ORDER: EventCategory[] = [
  'incident',
  'road',
  'infrastructure',
  'traffic',
  'safety',
  'waterlogging',
];

/** Simplified fleet route polylines (lat/lng vertices). */
export const ROUTE_PATHS: Record<string, [number, number][]> = {
  'R-01': [
    [25.49, 81.87],
    [25.468, 81.848],
    [25.456, 81.833],
    [25.452, 81.829],
    [25.447, 81.826],
    [25.436, 81.846],
  ],
  'R-02': [
    [25.418, 81.87],
    [25.44, 81.86],
    [25.455, 81.86],
    [25.462, 81.862],
    [25.468, 81.848],
  ],
  'R-03': [
    [25.442, 81.784],
    [25.447, 81.826],
    [25.452, 81.829],
    [25.456, 81.833],
    [25.459, 81.823],
  ],
  'R-04': [
    [25.43, 81.838],
    [25.436, 81.846],
    [25.44, 81.86],
    [25.425, 81.884],
  ],
};

export const ROUTE_NAMES: Record<string, string> = {
  'R-01': 'Teliarganj ↔ Zero Road',
  'R-02': 'Naini ↔ Georgetown',
  'R-03': 'Airport ↔ Civil Lines',
  'R-04': 'Chowk ↔ Sangam',
};
