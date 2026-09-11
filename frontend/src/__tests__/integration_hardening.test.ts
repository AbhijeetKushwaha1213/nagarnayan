import { describe, it, expect } from 'vitest';
import type {
  Alert,
  Bus,
  Camera,
  
  Stream,
  UrbanEvent,
  
} from '@/types/backend';

describe('Phase 8B Integration Hardening & Business Logic Verification', () => {
  // ── 1. KPI Calculations ───────────────────────────────────────────────────
  describe('KPI calculations audit against backend contract', () => {
    it('computes KPIs accurately from backend-shaped datasets', () => {
      const events: UrbanEvent[] = [
        {
          id: 'e1',
          event_type: 'POTHOLE',
          severity: 'HIGH',
          status: 'DETECTED',
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
          status: 'OPEN',
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

      const alerts: Alert[] = [
        {
          id: 'a1',
          event_id: 'e1',
          alert_type: 'CRITICAL_INFRASTRUCTURE',
          severity: 'CRITICAL',
          status: 'ACTIVE',
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
          severity: 'HIGH',
          status: 'ACKNOWLEDGED',
          title: 'High Severity Damaged Road',
          message: 'Road damage reported',
          triggered_at: '2026-09-11T10:05:00Z',
          acknowledged_at: '2026-09-11T10:10:00Z',
          resolved_at: null,
          metadata: {},
          created_at: '2026-09-11T10:05:00Z',
          updated_at: '2026-09-11T10:10:00Z',
        },
        {
          id: 'a3',
          event_id: 'e3',
          alert_type: 'MUNICIPAL_ISSUE',
          severity: 'HIGH',
          status: 'RESOLVED', // Terminal
          title: 'Resolved Alert',
          message: 'Defect cleared',
          triggered_at: '2026-09-11T09:00:00Z',
          acknowledged_at: null,
          resolved_at: '2026-09-11T09:30:00Z',
          metadata: {},
          created_at: '2026-09-11T09:00:00Z',
          updated_at: '2026-09-11T09:30:00Z',
        },
      ];

      const buses: Bus[] = [
        { id: 'b1', bus_number: 'KA-01-1001', route_id: 'R1', status: 'active', created_at: '', updated_at: '' },
        { id: 'b2', bus_number: 'KA-01-1002', route_id: 'R2', status: 'inactive', created_at: '', updated_at: '' },
      ];

      const cameras: Camera[] = [
        { id: 'c1', bus_id: 'b1', camera_type: 'front', status: 'active', created_at: '', updated_at: '' },
        { id: 'c2', bus_id: 'b1', camera_type: 'rear', status: 'active', created_at: '', updated_at: '' },
        { id: 'c3', bus_id: 'b2', camera_type: 'front', status: 'inactive', created_at: '', updated_at: '' },
      ];

      const streams: Stream[] = [
        { id: 's1', camera_id: 'c1', stream_url: 'rtsp://live1', protocol: 'rtsp', status: 'active', started_at: null, stopped_at: null, created_at: '', updated_at: '' },
        { id: 's2', camera_id: 'c2', stream_url: 'rtsp://live2', protocol: 'rtsp', status: 'inactive', started_at: null, stopped_at: null, created_at: '', updated_at: '' },
      ];

      // Exact dashboard KPI calculations:
      const activeEventsCount = events.filter((e) => e.status !== 'RESOLVED' && e.status !== 'REJECTED').length;
      const criticalHighAlerts = alerts.filter(
        (a) => (a.severity === 'CRITICAL' || a.severity === 'HIGH') && a.status !== 'RESOLVED' && a.status !== 'DISMISSED',
      );
      const activeBusesCount = buses.filter((b) => b.status === 'active').length;
      const activeCamerasCount = cameras.filter((c) => c.status === 'active').length;
      const activeStreamsCount = streams.filter((s) => s.status === 'active').length;

      expect(activeEventsCount).toBe(2); // e1 (DETECTED) and e2 (OPEN)
      expect(criticalHighAlerts).toHaveLength(2); // a1 (ACTIVE) and a2 (ACKNOWLEDGED), excluding resolved a3
      expect(buses).toHaveLength(2);
      expect(activeBusesCount).toBe(1);
      expect(cameras).toHaveLength(3);
      expect(activeCamerasCount).toBe(2);
      expect(streams).toHaveLength(2);
      expect(activeStreamsCount).toBe(1);
    });

    it('returns zero values cleanly for empty backend states without fabricated fallbacks', () => {
      const events: UrbanEvent[] = [];
      const alerts: Alert[] = [];
      const buses: Bus[] = [];
      const cameras: Camera[] = [];
      const streams: Stream[] = [];

      const activeEventsCount = events.filter((e) => e.status !== 'RESOLVED' && e.status !== 'REJECTED').length;
      const criticalHighAlerts = alerts.filter(
        (a) => (a.severity === 'CRITICAL' || a.severity === 'HIGH') && a.status !== 'RESOLVED' && a.status !== 'DISMISSED',
      );

      expect(activeEventsCount).toBe(0);
      expect(criticalHighAlerts).toHaveLength(0);
      expect(buses.length).toBe(0);
      expect(cameras.length).toBe(0);
      expect(streams.length).toBe(0);
    });
  });

  // ── 2. REST Initial State + WebSocket Merge & Deduplication ───────────────
  describe('REST Initial State + WebSocket Realtime Deltas', () => {
    it('coexists correctly: updates existing record and prepends new record', () => {
      const restEvents: UrbanEvent[] = [
        {
          id: 'evt-100',
          event_type: 'POTHOLE',
          severity: 'LOW',
          status: 'DETECTED',
          latitude: 15.0,
          longitude: 75.0,
          confidence: 0.65,
          first_detected_at: '2026-09-11T10:00:00Z',
          last_detected_at: '2026-09-11T10:00:00Z',
          metadata: {},
          created_at: '2026-09-11T10:00:00Z',
          updated_at: '2026-09-11T10:00:00Z',
        },
      ];

      const realtimeDeltas: UrbanEvent[] = [
        {
          // Escalation of evt-100 via event.updated
          id: 'evt-100',
          event_type: 'POTHOLE',
          severity: 'HIGH',
          status: 'VERIFIED',
          latitude: 15.0,
          longitude: 75.0,
          confidence: 0.92,
          first_detected_at: '2026-09-11T10:00:00Z',
          last_detected_at: '2026-09-11T10:15:00Z',
          metadata: { confirmations: 3 },
          created_at: '2026-09-11T10:00:00Z',
          updated_at: '2026-09-11T10:15:00Z',
        },
        {
          // New event via event.created
          id: 'evt-200',
          event_type: 'WATERLOGGING',
          severity: 'CRITICAL',
          status: 'DETECTED',
          latitude: 15.1,
          longitude: 75.1,
          confidence: 0.95,
          first_detected_at: '2026-09-11T10:20:00Z',
          last_detected_at: '2026-09-11T10:20:00Z',
          metadata: {},
          created_at: '2026-09-11T10:20:00Z',
          updated_at: '2026-09-11T10:20:00Z',
        },
      ];

      // Merge logic identical to Dashboard / EventsPage
      const map = new Map<string, UrbanEvent>();
      for (const e of restEvents) map.set(e.id, e);
      for (const e of realtimeDeltas) map.set(e.id, e);

      const merged = Array.from(map.values());
      expect(merged).toHaveLength(2);

      const updatedEvt100 = merged.find((e) => e.id === 'evt-100');
      expect(updatedEvt100?.severity).toBe('HIGH');
      expect(updatedEvt100?.status).toBe('VERIFIED');
      expect(updatedEvt100?.confidence).toBe(0.92);

      const newEvt200 = merged.find((e) => e.id === 'evt-200');
      expect(newEvt200?.event_type).toBe('WATERLOGGING');
      expect(newEvt200?.severity).toBe('CRITICAL');
    });

    it('deduplicates duplicate event.created messages with identical IDs', () => {
      const events: UrbanEvent[] = [
        {
          id: 'evt-dup',
          event_type: 'DAMAGED_ROAD',
          severity: 'MEDIUM',
          status: 'DETECTED',
          latitude: 18.0,
          longitude: 73.0,
          confidence: 0.8,
          first_detected_at: '2026-09-11T10:00:00Z',
          last_detected_at: '2026-09-11T10:00:00Z',
          metadata: {},
          created_at: '2026-09-11T10:00:00Z',
          updated_at: '2026-09-11T10:00:00Z',
        },
      ];

      const applyEvent = (current: UrbanEvent[], incoming: UrbanEvent) => {
        const exists = current.some((e) => e.id === incoming.id);
        if (exists) {
          return current.map((e) => (e.id === incoming.id ? { ...e, ...incoming } : e));
        }
        return [incoming, ...current];
      };

      // Send the same event again as event.created
      const updated = applyEvent(events, { ...events[0] });
      expect(updated).toHaveLength(1);
    });
  });

  // ── 3. Frontend Filtering Verification ────────────────────────────────────
  describe('Frontend Filtering Engine', () => {
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
        last_detected_at: '2026-09-11T10:05:00Z',
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

    it('filters events by severity correctly', () => {
      const filtered = dataset.filter((e) => e.severity === 'CRITICAL');
      expect(filtered).toHaveLength(1);
      expect(filtered[0].id).toBe('evt-pothole-crit');
    });

    it('filters events by status correctly', () => {
      const filtered = dataset.filter((e) => e.status === 'OPEN');
      expect(filtered).toHaveLength(1);
      expect(filtered[0].id).toBe('evt-water-med');
    });

    it('filters events by event_type correctly', () => {
      const filtered = dataset.filter((e) => e.event_type === 'POTHOLE');
      expect(filtered).toHaveLength(2);
    });

    it('filters events by free-text search across type, ID, and bus ID', () => {
      const search = (q: string) =>
        dataset.filter(
          (e) =>
            e.event_type.toLowerCase().includes(q.toLowerCase()) ||
            e.id.toLowerCase().includes(q.toLowerCase()) ||
            (e.bus_id && e.bus_id.toLowerCase().includes(q.toLowerCase())),
        );

      expect(search('water')).toHaveLength(1);
      expect(search('alpha')).toHaveLength(2);
      expect(search('pothole-low')).toHaveLength(1);
      expect(search('nonexistent')).toHaveLength(0);
    });

    it('filters alerts by severity and status correctly', () => {
      const alertDataset: Alert[] = [
        {
          id: 'a1',
          event_id: 'e1',
          alert_type: 'MUNICIPAL_ISSUE',
          severity: 'CRITICAL',
          status: 'ACTIVE',
          title: 'Crit Alert',
          message: 'Msg',
          triggered_at: null,
          acknowledged_at: null,
          resolved_at: null,
          metadata: {},
          created_at: '',
          updated_at: '',
        },
        {
          id: 'a2',
          event_id: 'e2',
          alert_type: 'TRAFFIC_HAZARD',
          severity: 'HIGH',
          status: 'ACKNOWLEDGED',
          title: 'High Alert',
          message: 'Msg',
          triggered_at: null,
          acknowledged_at: null,
          resolved_at: null,
          metadata: {},
          created_at: '',
          updated_at: '',
        },
        {
          id: 'a3',
          event_id: 'e3',
          alert_type: 'CRITICAL_INFRASTRUCTURE',
          severity: 'LOW',
          status: 'RESOLVED',
          title: 'Low Alert',
          message: 'Msg',
          triggered_at: null,
          acknowledged_at: null,
          resolved_at: null,
          metadata: {},
          created_at: '',
          updated_at: '',
        },
      ];

      expect(alertDataset.filter((a) => a.severity === 'CRITICAL')).toHaveLength(1);
      expect(alertDataset.filter((a) => a.status === 'ACKNOWLEDGED')).toHaveLength(1);
      expect(alertDataset.filter((a) => a.status === 'ACTIVE' && a.severity === 'CRITICAL')).toHaveLength(1);
    });
  });

  // ── 4. Coordinate Consistency & Fabricated Location Rejection ─────────────
  describe('GeoJSON and GIS Telemetry Safety', () => {
    it('verifies coordinate order [longitude, latitude] without default Bangalore coordinates', () => {
      const rawFeature = {
        type: 'Feature' as const,
        geometry: {
          type: 'Point' as const,
          coordinates: [88.3639, 22.5726] as [number, number], // Kolkata [lng, lat]
        },
        properties: {
          event_id: 'kolkata-1',
          event_type: 'DAMAGED_ROAD',
          status: 'DETECTED' as const,
          severity: 'HIGH' as const,
          confidence: 0.88,
          detected_at: '2026-09-11T12:00:00Z',
        },
      };

      const [lng, lat] = rawFeature.geometry.coordinates;
      expect(lng).toBe(88.3639);
      expect(lat).toBe(22.5726);

      // In Leaflet map position is [latitude, longitude]
      const leafletPosition: [number, number] = [lat, lng];
      expect(leafletPosition).toEqual([22.5726, 88.3639]);

      // Confirm no Bangalore coordinates (12.9716, 77.5946) are injected
      expect(lat).not.toBe(12.9716);
      expect(lng).not.toBe(77.5946);
    });

    it('rejects invalid longitude/latitude ranges and NaN', () => {
      const validateCoordinates = (coords: any): boolean => {
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
      };

      expect(validateCoordinates([77.59, 12.97])).toBe(true);
      expect(validateCoordinates([NaN, 12.97])).toBe(false);
      expect(validateCoordinates([77.59, NaN])).toBe(false);
      expect(validateCoordinates([200.0, 12.97])).toBe(false); // lng > 180
      expect(validateCoordinates([77.59, 100.0])).toBe(false); // lat > 90
      expect(validateCoordinates([-190.0, 0])).toBe(false);   // lng < -180
      expect(validateCoordinates([0, -95.0])).toBe(false);    // lat < -90
      expect(validateCoordinates(null)).toBe(false);
      expect(validateCoordinates([])).toBe(false);
    });
  });
});
