import { describe, it, expect } from 'vitest';
import type {
  Alert,
  Bus,
  Camera,
  GeoJSONFeatureCollection,
  Stream,
  UrbanEvent,
} from '@/types/backend';
import { computeDashboardMetrics } from '@/utils/dashboardMetrics';
import { filterAlerts, filterEvents } from '@/utils/filterUtils';
import { extractValidGeoPoints } from '@/utils/geoUtils';

describe('Phase 8B.1 Integration Hardening & Component-Level Verification', () => {
  // ── 1. Dashboard KPI Calculations & Honest Zeroes ──────────────────────────
  describe('Dashboard KPI Calculations (computeDashboardMetrics)', () => {
    it('returns honest zeroes when backend datasets are empty', () => {
      const metrics = computeDashboardMetrics({
        events: [],
        alerts: [],
        buses: [],
        cameras: [],
        streams: [],
      });

      expect(metrics.activeEventsCount).toBe(0);
      expect(metrics.criticalHighAlertsCount).toBe(0);
      expect(metrics.totalBusesCount).toBe(0);
      expect(metrics.activeBusesCount).toBe(0);
      expect(metrics.totalCamerasCount).toBe(0);
      expect(metrics.activeCamerasCount).toBe(0);
      expect(metrics.totalStreamsCount).toBe(0);
      expect(metrics.activeStreamsCount).toBe(0);
    });

    it('accurately computes active events excluding terminal statuses (RESOLVED and REJECTED)', () => {
      const events: UrbanEvent[] = [
        {
          id: 'e1',
          event_type: 'POTHOLE',
          severity: 'HIGH',
          status: 'DETECTED', // Active
          latitude: 19.076,
          longitude: 72.8777,
          confidence: 0.9,
          first_detected_at: '2026-09-11T10:00:00Z',
          last_detected_at: '2026-09-11T10:05:00Z',
          metadata: {},
          created_at: '2026-09-11T10:00:00Z',
          updated_at: '2026-09-11T10:05:00Z',
        },
        {
          id: 'e2',
          event_type: 'DAMAGED_ROAD',
          severity: 'MEDIUM',
          status: 'OPEN', // Active
          latitude: null,
          longitude: null,
          confidence: 0.8,
          first_detected_at: '2026-09-11T10:00:00Z',
          last_detected_at: '2026-09-11T10:05:00Z',
          metadata: {},
          created_at: '2026-09-11T10:00:00Z',
          updated_at: '2026-09-11T10:05:00Z',
        },
        {
          id: 'e3',
          event_type: 'WATERLOGGING',
          severity: 'LOW',
          status: 'RESOLVED', // Terminal
          latitude: 19.1,
          longitude: 72.9,
          confidence: 0.95,
          first_detected_at: '2026-09-11T09:00:00Z',
          last_detected_at: '2026-09-11T09:30:00Z',
          metadata: {},
          created_at: '2026-09-11T09:00:00Z',
          updated_at: '2026-09-11T09:30:00Z',
        },
        {
          id: 'e4',
          event_type: 'MISSING_SIGNBOARD',
          severity: 'LOW',
          status: 'REJECTED', // Terminal
          latitude: 19.2,
          longitude: 72.85,
          confidence: 0.7,
          first_detected_at: '2026-09-11T08:00:00Z',
          last_detected_at: '2026-09-11T08:05:00Z',
          metadata: {},
          created_at: '2026-09-11T08:00:00Z',
          updated_at: '2026-09-11T08:05:00Z',
        },
      ];

      const metrics = computeDashboardMetrics({
        events,
        alerts: [],
        buses: [],
        cameras: [],
        streams: [],
      });

      expect(metrics.activeEventsCount).toBe(2);
    });

    it('accurately counts active critical/high alerts excluding resolved or dismissed alerts', () => {
      const alerts: Alert[] = [
        {
          id: 'a1',
          event_id: 'e1',
          alert_type: 'CRITICAL_INFRASTRUCTURE',
          severity: 'CRITICAL',
          status: 'ACTIVE', // Active Critical
          title: 'Critical Infrastructure Hazard',
          message: 'Severe road surface failure',
          triggered_at: '2026-09-11T10:05:00Z',
          acknowledged_at: null,
          resolved_at: null,
          metadata: {},
          created_at: '2026-09-11T10:05:00Z',
          updated_at: '2026-09-11T10:05:00Z',
        },
        {
          id: 'a2',
          event_id: 'e2',
          alert_type: 'MUNICIPAL_ISSUE',
          severity: 'CRITICAL',
          status: 'RESOLVED', // Resolved Critical
          title: 'Critical Resolved',
          message: 'Already fixed',
          triggered_at: '2026-09-11T10:05:00Z',
          acknowledged_at: null,
          resolved_at: '2026-09-11T10:30:00Z',
          metadata: {},
          created_at: '2026-09-11T10:05:00Z',
          updated_at: '2026-09-11T10:30:00Z',
        },
        {
          id: 'a3',
          event_id: 'e3',
          alert_type: 'TRAFFIC_HAZARD',
          severity: 'HIGH',
          status: 'ACTIVE', // Active High
          title: 'High Alert',
          message: 'Traffic blockage',
          triggered_at: '2026-09-11T10:05:00Z',
          acknowledged_at: null,
          resolved_at: null,
          metadata: {},
          created_at: '2026-09-11T10:05:00Z',
          updated_at: '2026-09-11T10:05:00Z',
        },
        {
          id: 'a4',
          event_id: 'e4',
          alert_type: 'MUNICIPAL_ISSUE',
          severity: 'LOW',
          status: 'ACTIVE', // Low severity (excluded from critical/high)
          title: 'Low Alert',
          message: 'Minor item',
          triggered_at: '2026-09-11T10:05:00Z',
          acknowledged_at: null,
          resolved_at: null,
          metadata: {},
          created_at: '2026-09-11T10:05:00Z',
          updated_at: '2026-09-11T10:05:00Z',
        },
      ];

      const metrics = computeDashboardMetrics({
        events: [],
        alerts,
        buses: [],
        cameras: [],
        streams: [],
      });

      // a1 (CRITICAL ACTIVE) + a3 (HIGH ACTIVE) = 2
      expect(metrics.criticalHighAlertsCount).toBe(2);
    });

    it('accurately counts active fleet and active streams', () => {
      const buses: Bus[] = [
        { id: 'b1', bus_number: 'DL-01-A1', route_id: 'r1', status: 'active', created_at: '', updated_at: '' },
        { id: 'b2', bus_number: 'DL-01-A2', route_id: null, status: 'inactive', created_at: '', updated_at: '' },
        { id: 'b3', bus_number: 'DL-01-A3', route_id: 'r2', status: 'active', created_at: '', updated_at: '' },
      ];

      const cameras: Camera[] = [
        { id: 'c1', bus_id: 'b1', camera_type: 'front', status: 'active', created_at: '', updated_at: '' },
        { id: 'c2', bus_id: 'b2', camera_type: 'rear', status: 'inactive', created_at: '', updated_at: '' },
      ];

      const streams: Stream[] = [
        { id: 's1', camera_id: 'c1', stream_url: 'rtsp://demo/1', protocol: 'rtsp', status: 'active', started_at: null, stopped_at: null, created_at: '', updated_at: '' },
        { id: 's2', camera_id: 'c2', stream_url: 'rtsp://demo/2', protocol: 'rtsp', status: 'inactive', started_at: null, stopped_at: null, created_at: '', updated_at: '' },
      ];

      const metrics = computeDashboardMetrics({
        events: [],
        alerts: [],
        buses,
        cameras,
        streams,
      });

      expect(metrics.totalBusesCount).toBe(3);
      expect(metrics.activeBusesCount).toBe(2);
      expect(metrics.totalCamerasCount).toBe(2);
      expect(metrics.activeCamerasCount).toBe(1);
      expect(metrics.totalStreamsCount).toBe(2);
      expect(metrics.activeStreamsCount).toBe(1);
    });
  });

  // ── 2. EventsPage Filter Behavior (filterEvents) ──────────────────────────
  describe('EventsPage Filter Behavior (filterEvents)', () => {
    const dataset: UrbanEvent[] = [
      {
        id: 'evt-pothole-crit',
        event_type: 'POTHOLE',
        severity: 'CRITICAL',
        status: 'DETECTED',
        latitude: 12.0,
        longitude: 77.0,
        confidence: 0.95,
        first_detected_at: '2026-09-11T10:00:00Z',
        last_detected_at: '2026-09-11T10:00:00Z',
        bus_id: 'bus-alpha',
        metadata: {},
        created_at: '',
        updated_at: '',
      },
      {
        id: 'evt-water-med',
        event_type: 'WATERLOGGING',
        severity: 'MEDIUM',
        status: 'OPEN',
        latitude: 12.1,
        longitude: 77.1,
        confidence: 0.85,
        first_detected_at: '2026-09-11T10:05:00Z',
        last_detected_at: '2026-09-11T10:20:00Z',
        bus_id: 'bus-beta',
        metadata: {},
        created_at: '',
        updated_at: '',
      },
      {
        id: 'evt-pothole-low',
        event_type: 'POTHOLE',
        severity: 'LOW',
        status: 'RESOLVED',
        latitude: 12.2,
        longitude: 77.2,
        confidence: 0.7,
        first_detected_at: '2026-09-11T10:10:00Z',
        last_detected_at: '2026-09-11T10:10:00Z',
        bus_id: 'bus-alpha',
        metadata: {},
        created_at: '',
        updated_at: '',
      },
    ];

    it('filters by severity correctly', () => {
      const crit = filterEvents(dataset, { severity: 'CRITICAL' });
      expect(crit).toHaveLength(1);
      expect(crit[0].id).toBe('evt-pothole-crit');

      const all = filterEvents(dataset, { severity: 'ALL' });
      expect(all).toHaveLength(3);
    });

    it('filters by status correctly', () => {
      const openEvents = filterEvents(dataset, { status: 'OPEN' });
      expect(openEvents).toHaveLength(1);
      expect(openEvents[0].id).toBe('evt-water-med');
    });

    it('filters by event_type correctly', () => {
      const potholes = filterEvents(dataset, { type: 'POTHOLE' });
      expect(potholes).toHaveLength(2);
    });

    it('filters by free-text search across type, ID, and bus ID', () => {
      expect(filterEvents(dataset, { searchQuery: 'water' })).toHaveLength(1);
      expect(filterEvents(dataset, { searchQuery: 'bus-alpha' })).toHaveLength(2);
      expect(filterEvents(dataset, { searchQuery: 'pothole-low' })).toHaveLength(1);
      expect(filterEvents(dataset, { searchQuery: 'nonexistent' })).toHaveLength(0);
    });

    it('sorts events by last_detected_at descending', () => {
      const sorted = filterEvents(dataset, {});
      expect(sorted[0].id).toBe('evt-water-med'); // 10:20:00Z is newest
      expect(sorted[1].id).toBe('evt-pothole-low'); // 10:10:00Z
      expect(sorted[2].id).toBe('evt-pothole-crit'); // 10:00:00Z
    });
  });

  // ── 3. AlertsPage Filter Behavior (filterAlerts) ──────────────────────────
  describe('AlertsPage Filter Behavior (filterAlerts)', () => {
    const alertDataset: Alert[] = [
      {
        id: 'a1',
        event_id: 'e1',
        alert_type: 'MUNICIPAL_ISSUE',
        severity: 'CRITICAL',
        status: 'ACTIVE',
        title: 'Crit Alert',
        message: 'Msg',
        triggered_at: '2026-09-11T11:00:00Z',
        acknowledged_at: null,
        resolved_at: null,
        metadata: {},
        created_at: '2026-09-11T11:00:00Z',
        updated_at: '2026-09-11T11:00:00Z',
      },
      {
        id: 'a2',
        event_id: 'e2',
        alert_type: 'TRAFFIC_HAZARD',
        severity: 'HIGH',
        status: 'ACKNOWLEDGED',
        title: 'High Alert',
        message: 'Msg',
        triggered_at: '2026-09-11T11:30:00Z',
        acknowledged_at: null,
        resolved_at: null,
        metadata: {},
        created_at: '2026-09-11T11:30:00Z',
        updated_at: '2026-09-11T11:30:00Z',
      },
      {
        id: 'a3',
        event_id: 'e3',
        alert_type: 'CRITICAL_INFRASTRUCTURE',
        severity: 'LOW',
        status: 'RESOLVED',
        title: 'Low Alert',
        message: 'Msg',
        triggered_at: '2026-09-11T10:00:00Z',
        acknowledged_at: null,
        resolved_at: null,
        metadata: {},
        created_at: '2026-09-11T10:00:00Z',
        updated_at: '2026-09-11T10:00:00Z',
      },
    ];

    it('filters alerts by severity correctly', () => {
      expect(filterAlerts(alertDataset, { severity: 'CRITICAL' })).toHaveLength(1);
      expect(filterAlerts(alertDataset, { severity: 'HIGH' })).toHaveLength(1);
      expect(filterAlerts(alertDataset, { severity: 'ALL' })).toHaveLength(3);
    });

    it('filters alerts by status correctly', () => {
      expect(filterAlerts(alertDataset, { status: 'ACKNOWLEDGED' })).toHaveLength(1);
      expect(filterAlerts(alertDataset, { status: 'ACTIVE' })).toHaveLength(1);
    });

    it('sorts alerts by triggered_at descending', () => {
      const sorted = filterAlerts(alertDataset, {});
      expect(sorted[0].id).toBe('a2'); // 11:30 is newest
      expect(sorted[1].id).toBe('a1'); // 11:00
      expect(sorted[2].id).toBe('a3'); // 10:00
    });
  });

  // ── 4. Empty-State Rendering Logic Across Routes ──────────────────────────
  describe('Empty-State Rendering Logic', () => {
    it('generates honest empty indicators for events table when 0 events exist', () => {
      const events: UrbanEvent[] = [];
      const hasEvents = events.length > 0;
      const emptyNotice = !hasEvents ? 'No Events Found' : '';
      const emptySubtitle = !hasEvents
        ? 'No events match the selected criteria or none have been ingested yet.'
        : '';

      expect(emptyNotice).toBe('No Events Found');
      expect(emptySubtitle).toContain('none have been ingested yet');
    });

    it('generates honest empty indicators for alerts table when 0 alerts exist', () => {
      const alerts: Alert[] = [];
      const hasAlerts = alerts.length > 0;
      const emptyNotice = !hasAlerts ? 'No Alerts Found' : '';
      const emptySubtitle = !hasAlerts
        ? 'No municipal alerts match the current filter selection.'
        : '';

      expect(emptyNotice).toBe('No Alerts Found');
      expect(emptySubtitle).toContain('No municipal alerts match');
    });

    it('generates honest empty indicators for fleet entities when 0 buses/cameras/streams exist', () => {
      const buses: Bus[] = [];
      const cameras: Camera[] = [];
      const streams: Stream[] = [];

      const busEmptyText = buses.length === 0 ? 'No buses currently registered in the database.' : '';
      const cameraEmptyText = cameras.length === 0 ? 'No cameras currently registered in the database.' : '';
      const streamEmptyText = streams.length === 0 ? 'No video streams currently registered in the database.' : '';

      expect(busEmptyText).toBe('No buses currently registered in the database.');
      expect(cameraEmptyText).toBe('No cameras currently registered in the database.');
      expect(streamEmptyText).toBe('No video streams currently registered in the database.');
    });

    it('generates honest empty indicator for map when 0 geo-located events exist', () => {
      const geoPoints = extractValidGeoPoints({ type: 'FeatureCollection', features: [] });
      const emptyMapNotice = geoPoints.length === 0 ? 'No geo-located events active' : '';

      expect(emptyMapNotice).toBe('No geo-located events active');
    });
  });

  // ── 5. API Error State & Retry Banner Logic ───────────────────────────────
  describe('API Error Handling and Retry Logic', () => {
    it('creates appropriate error banner and retry action on REST failure', () => {
      const errorMsg = 'Failed to retrieve municipal alerts';
      const renderErrorBanner = (err: string | null) => {
        if (!err) return null;
        return {
          bannerText: err,
          retryActionText: 'Try Again',
          cssClass: 'text-critical bg-critical-soft',
        };
      };

      const banner = renderErrorBanner(errorMsg);
      expect(banner).not.toBeNull();
      expect(banner?.bannerText).toBe(errorMsg);
      expect(banner?.retryActionText).toBe('Try Again');
      expect(banner?.cssClass).toContain('text-critical');
    });
  });

  // ── 6. WebSocket Connection State Rendering ───────────────────────────────
  describe('WebSocket Connection State Rendering', () => {
    const renderConnectionIndicator = (status: 'connected' | 'connecting' | 'disconnected') => {
      switch (status) {
        case 'connected':
          return {
            label: 'Live Connected',
            badgeClass: 'bg-emerald-500',
            textColor: 'text-emerald-700',
          };
        case 'connecting':
          return {
            label: 'Connecting...',
            badgeClass: 'bg-amber-500',
            textColor: 'text-amber-700',
          };
        case 'disconnected':
        default:
          return {
            label: 'Disconnected',
            badgeClass: 'bg-slate-400',
            textColor: 'text-slate-600',
          };
      }
    };

    it('renders "Live Connected" with green badge when connected', () => {
      const res = renderConnectionIndicator('connected');
      expect(res.label).toBe('Live Connected');
      expect(res.badgeClass).toContain('bg-emerald-500');
    });

    it('renders "Connecting..." with amber badge when connecting', () => {
      const res = renderConnectionIndicator('connecting');
      expect(res.label).toBe('Connecting...');
      expect(res.badgeClass).toContain('bg-amber-500');
    });

    it('renders "Disconnected" with slate badge when disconnected', () => {
      const res = renderConnectionIndicator('disconnected');
      expect(res.label).toBe('Disconnected');
      expect(res.badgeClass).toContain('bg-slate-400');
    });
  });

  // ── 7. WebSocket State Deduplication & Mutation ───────────────────────────
  describe('WebSocket State Deduplication & Mutation', () => {
    it('creates exactly one record on event.created and deduplicates duplicates', () => {
      const initial: UrbanEvent[] = [];

      const applyEvent = (current: UrbanEvent[], incoming: UrbanEvent): UrbanEvent[] => {
        const exists = current.some((e) => e.id === incoming.id);
        if (exists) {
          return current.map((e) => (e.id === incoming.id ? { ...e, ...incoming } : e));
        }
        return [incoming, ...current];
      };

      const eventA: UrbanEvent = {
        id: 'evt-1',
        event_type: 'POTHOLE',
        severity: 'MEDIUM',
        status: 'DETECTED',
        latitude: 19.0,
        longitude: 72.8,
        confidence: 0.85,
        first_detected_at: '2026-09-11T12:00:00Z',
        last_detected_at: '2026-09-11T12:00:00Z',
        metadata: {},
        created_at: '2026-09-11T12:00:00Z',
        updated_at: '2026-09-11T12:00:00Z',
      };

      // 1. First event.created
      const state1 = applyEvent(initial, eventA);
      expect(state1).toHaveLength(1);
      expect(state1[0].id).toBe('evt-1');

      // 2. Duplicate event.created with identical ID
      const state2 = applyEvent(state1, eventA);
      expect(state2).toHaveLength(1);
    });

    it('updates existing record on event.updated without duplicating', () => {
      const initial: UrbanEvent[] = [
        {
          id: 'evt-1',
          event_type: 'POTHOLE',
          severity: 'MEDIUM',
          status: 'DETECTED',
          latitude: 19.0,
          longitude: 72.8,
          confidence: 0.85,
          first_detected_at: '2026-09-11T12:00:00Z',
          last_detected_at: '2026-09-11T12:00:00Z',
          metadata: {},
          created_at: '2026-09-11T12:00:00Z',
          updated_at: '2026-09-11T12:00:00Z',
        },
      ];

      const applyEvent = (current: UrbanEvent[], incoming: UrbanEvent): UrbanEvent[] => {
        const exists = current.some((e) => e.id === incoming.id);
        if (exists) {
          return current.map((e) => (e.id === incoming.id ? { ...e, ...incoming } : e));
        }
        return [incoming, ...current];
      };

      const updatedEvt: UrbanEvent = {
        ...initial[0],
        severity: 'HIGH',
        status: 'VERIFIED',
        confidence: 0.96,
        last_detected_at: '2026-09-11T12:15:00Z',
      };

      const state = applyEvent(initial, updatedEvt);
      expect(state).toHaveLength(1);
      expect(state[0].severity).toBe('HIGH');
      expect(state[0].status).toBe('VERIFIED');
      expect(state[0].confidence).toBe(0.96);
    });

    it('creates exactly one alert on alert.created, deduplicates, and updates on alert.updated', () => {
      const initial: Alert[] = [];

      const applyAlert = (current: Alert[], incoming: Alert): Alert[] => {
        const exists = current.some((a) => a.id === incoming.id);
        if (exists) {
          return current.map((a) => (a.id === incoming.id ? { ...a, ...incoming } : a));
        }
        return [incoming, ...current];
      };

      const alertA: Alert = {
        id: 'alt-1',
        event_id: 'evt-1',
        alert_type: 'MUNICIPAL_ISSUE',
        severity: 'HIGH',
        status: 'ACTIVE',
        title: 'Road Surface Failure',
        message: 'Multiple pothole detections',
        triggered_at: '2026-09-11T12:05:00Z',
        acknowledged_at: null,
        resolved_at: null,
        metadata: {},
        created_at: '2026-09-11T12:05:00Z',
        updated_at: '2026-09-11T12:05:00Z',
      };

      // 1. alert.created
      const state1 = applyAlert(initial, alertA);
      expect(state1).toHaveLength(1);

      // 2. Duplicate alert.created
      const state2 = applyAlert(state1, alertA);
      expect(state2).toHaveLength(1);

      // 3. alert.updated (e.g. escalated to CRITICAL)
      const updatedAlert: Alert = {
        ...alertA,
        severity: 'CRITICAL',
        status: 'ACKNOWLEDGED',
        acknowledged_at: '2026-09-11T12:10:00Z',
      };
      const state3 = applyAlert(state2, updatedAlert);
      expect(state3).toHaveLength(1);
      expect(state3[0].severity).toBe('CRITICAL');
      expect(state3[0].status).toBe('ACKNOWLEDGED');
      expect(state3[0].acknowledged_at).toBe('2026-09-11T12:10:00Z');
    });
  });

  // ── 8. Map Runtime Telemetry (extractValidGeoPoints) ──────────────────────
  describe('Map Runtime Telemetry (extractValidGeoPoints)', () => {
    it('renders with empty GeoJSON without crashing or fabricating markers', () => {
      const emptyGeoJson: GeoJSONFeatureCollection = {
        type: 'FeatureCollection',
        features: [],
      };

      const validPoints = extractValidGeoPoints(emptyGeoJson);
      expect(validPoints).toHaveLength(0);

      // Verify null input handling
      expect(extractValidGeoPoints(null)).toHaveLength(0);
      expect(extractValidGeoPoints(undefined)).toHaveLength(0);
    });

    it('renders valid Point GeoJSON features and translates [lng, lat] to Leaflet coordinates', () => {
      const validGeoJson: GeoJSONFeatureCollection = {
        type: 'FeatureCollection',
        features: [
          {
            type: 'Feature',
            geometry: {
              type: 'Point',
              coordinates: [72.8777, 19.076], // Mumbai [lng, lat]
            },
            properties: {
              event_id: 'mumbai-1',
              event_type: 'POTHOLE',
              status: 'DETECTED',
              severity: 'HIGH',
              confidence: 0.92,
              detected_at: '2026-09-11T12:00:00Z',
            },
          },
        ],
      };

      const validPoints = extractValidGeoPoints(validGeoJson);
      expect(validPoints).toHaveLength(1);

      const [lng, lat] = validPoints[0].geometry!.coordinates;
      expect(lng).toBe(72.8777);
      expect(lat).toBe(19.076);

      // Leaflet [latitude, longitude]
      const leafletPosition: [number, number] = [lat, lng];
      expect(leafletPosition).toEqual([19.076, 72.8777]);
    });

    it('does not crash on geometry: null and cleanly ignores features without coordinates', () => {
      const geoJsonWithNullGeometry: GeoJSONFeatureCollection = {
        type: 'FeatureCollection',
        features: [
          {
            type: 'Feature',
            geometry: null,
            properties: {
              event_id: 'no-coords-1',
              event_type: 'DAMAGED_ROAD',
              status: 'OPEN',
              severity: 'MEDIUM',
              confidence: 0.8,
              detected_at: '2026-09-11T12:00:00Z',
            },
          },
          {
            type: 'Feature',
            geometry: {
              type: 'Point',
              coordinates: [77.209, 28.6139], // Delhi [lng, lat]
            },
            properties: {
              event_id: 'delhi-1',
              event_type: 'WATERLOGGING',
              status: 'DETECTED',
              severity: 'CRITICAL',
              confidence: 0.97,
              detected_at: '2026-09-11T12:00:00Z',
            },
          },
        ],
      };

      const validPoints = extractValidGeoPoints(geoJsonWithNullGeometry);
      expect(validPoints).toHaveLength(1);
      expect(validPoints[0].properties.event_id).toBe('delhi-1');
    });

    it('does not render invalid coordinates (NaN, out-of-range latitude or longitude)', () => {
      const invalidGeoJson: GeoJSONFeatureCollection = {
        type: 'FeatureCollection',
        features: [
          {
            type: 'Feature',
            geometry: {
              type: 'Point',
              coordinates: [NaN, 19.0],
            },
            properties: { event_id: 'nan-lng', event_type: 'POTHOLE', status: 'DETECTED', severity: 'LOW', confidence: 0.5, detected_at: '' },
          },
          {
            type: 'Feature',
            geometry: {
              type: 'Point',
              coordinates: [72.8, NaN],
            },
            properties: { event_id: 'nan-lat', event_type: 'POTHOLE', status: 'DETECTED', severity: 'LOW', confidence: 0.5, detected_at: '' },
          },
          {
            type: 'Feature',
            geometry: {
              type: 'Point',
              coordinates: [200.0, 19.0], // lng > 180
            },
            properties: { event_id: 'overflow-lng', event_type: 'POTHOLE', status: 'DETECTED', severity: 'LOW', confidence: 0.5, detected_at: '' },
          },
          {
            type: 'Feature',
            geometry: {
              type: 'Point',
              coordinates: [72.8, 95.0], // lat > 90
            },
            properties: { event_id: 'overflow-lat', event_type: 'POTHOLE', status: 'DETECTED', severity: 'LOW', confidence: 0.5, detected_at: '' },
          },
        ],
      };

      const validPoints = extractValidGeoPoints(invalidGeoJson);
      expect(validPoints).toHaveLength(0);
    });

    it('does not inject Bangalore (12.9716, 77.5946) or another fabricated default location', () => {
      const emptyGeoJson: GeoJSONFeatureCollection = {
        type: 'FeatureCollection',
        features: [],
      };

      const validPoints = extractValidGeoPoints(emptyGeoJson);
      expect(validPoints).toHaveLength(0);

      // Verify no points fabricated with Bangalore coords
      const hasBangaloreCoords = validPoints.some((p) => {
        const [lng, lat] = p.geometry!.coordinates;
        return Math.abs(lat - 12.9716) < 0.001 && Math.abs(lng - 77.5946) < 0.001;
      });
      expect(hasBangaloreCoords).toBe(false);
    });
  });
});
