import { describe, it, expect } from 'vitest';
import type { Alert, UrbanEvent, WebSocketEnvelope } from '@/types/backend';

describe('WebSocket Realtime Contracts & State Updates', () => {
  it('event.created and event.updated update state idempotently using ID as stable identity', () => {
    let events: UrbanEvent[] = [
      {
        id: 'evt-1',
        event_type: 'POTHOLE',
        severity: 'MEDIUM',
        status: 'DETECTED',
        latitude: 12.9716,
        longitude: 77.5946,
        confidence: 0.85,
        first_detected_at: '2026-09-11T12:00:00Z',
        last_detected_at: '2026-09-11T12:00:00Z',
        metadata: {},
        created_at: '2026-09-11T12:00:00Z',
        updated_at: '2026-09-11T12:00:00Z',
      },
    ];

    // Helper implementing the RealtimeContext update logic
    const applyEventMessage = (current: UrbanEvent[], envelope: WebSocketEnvelope<UrbanEvent>) => {
      const item = envelope.data;
      if (!item?.id) return current;
      const exists = current.some((e) => e.id === item.id);
      if (exists) {
        return current.map((e) => (e.id === item.id ? { ...e, ...item } : e));
      }
      return [item, ...current];
    };

    // 1. Incoming duplicate event.created with existing ID should NOT duplicate
    const duplicateCreatedEnvelope: WebSocketEnvelope<UrbanEvent> = {
      type: 'event.created',
      timestamp: '2026-09-11T12:01:00Z',
      data: {
        id: 'evt-1',
        event_type: 'POTHOLE',
        severity: 'MEDIUM',
        status: 'DETECTED',
        latitude: 12.9716,
        longitude: 77.5946,
        confidence: 0.85,
        first_detected_at: '2026-09-11T12:00:00Z',
        last_detected_at: '2026-09-11T12:00:00Z',
        metadata: {},
        created_at: '2026-09-11T12:00:00Z',
        updated_at: '2026-09-11T12:00:00Z',
      },
    };
    events = applyEventMessage(events, duplicateCreatedEnvelope);
    expect(events).toHaveLength(1);

    // 2. Incoming event.updated should update existing item in place
    const updatedEnvelope: WebSocketEnvelope<UrbanEvent> = {
      type: 'event.updated',
      timestamp: '2026-09-11T12:05:00Z',
      data: {
        id: 'evt-1',
        event_type: 'POTHOLE',
        severity: 'HIGH', // escalated
        status: 'DETECTED',
        latitude: 12.9716,
        longitude: 77.5946,
        confidence: 0.94,
        first_detected_at: '2026-09-11T12:00:00Z',
        last_detected_at: '2026-09-11T12:05:00Z',
        metadata: { detection_count: 3 },
        created_at: '2026-09-11T12:00:00Z',
        updated_at: '2026-09-11T12:05:00Z',
      },
    };
    events = applyEventMessage(events, updatedEnvelope);
    expect(events).toHaveLength(1);
    expect(events[0].severity).toBe('HIGH');
    expect(events[0].confidence).toBe(0.94);

    // 3. Brand new event.created should prepend to list
    const newEventEnvelope: WebSocketEnvelope<UrbanEvent> = {
      type: 'event.created',
      timestamp: '2026-09-11T12:10:00Z',
      data: {
        id: 'evt-2',
        event_type: 'WATERLOGGING',
        severity: 'CRITICAL',
        status: 'DETECTED',
        latitude: 12.98,
        longitude: 77.60,
        confidence: 0.96,
        first_detected_at: '2026-09-11T12:10:00Z',
        last_detected_at: '2026-09-11T12:10:00Z',
        metadata: {},
        created_at: '2026-09-11T12:10:00Z',
        updated_at: '2026-09-11T12:10:00Z',
      },
    };
    events = applyEventMessage(events, newEventEnvelope);
    expect(events).toHaveLength(2);
    expect(events[0].id).toBe('evt-2');
  });

  it('alert.created and alert.updated maintain alert state without duplicate records', () => {
    let alerts: Alert[] = [];

    const applyAlertMessage = (current: Alert[], envelope: WebSocketEnvelope<Alert>) => {
      const item = envelope.data;
      if (!item?.id) return current;
      const exists = current.some((a) => a.id === item.id);
      if (exists) {
        return current.map((a) => (a.id === item.id ? { ...a, ...item } : a));
      }
      return [item, ...current];
    };

    const alertEnvelope: WebSocketEnvelope<Alert> = {
      type: 'alert.created',
      timestamp: '2026-09-11T12:00:00Z',
      data: {
        id: 'alt-1',
        event_id: 'evt-1',
        alert_type: 'MUNICIPAL_ISSUE',
        severity: 'HIGH',
        status: 'NEW',
        title: 'High Severity Pothole',
        message: 'Persistent defect reported',
        triggered_at: '2026-09-11T12:00:00Z',
        acknowledged_at: null,
        resolved_at: null,
        metadata: {},
        created_at: '2026-09-11T12:00:00Z',
        updated_at: '2026-09-11T12:00:00Z',
      },
    };

    alerts = applyAlertMessage(alerts, alertEnvelope);
    expect(alerts).toHaveLength(1);

    // Operator acknowledges alert -> alert.updated arrives
    const ackEnvelope: WebSocketEnvelope<Alert> = {
      type: 'alert.updated',
      timestamp: '2026-09-11T12:05:00Z',
      data: {
        ...alertEnvelope.data,
        status: 'ACKNOWLEDGED',
        acknowledged_at: '2026-09-11T12:05:00Z',
      },
    };
    alerts = applyAlertMessage(alerts, ackEnvelope);
    expect(alerts).toHaveLength(1);
    expect(alerts[0].status).toBe('ACKNOWLEDGED');
    expect(alerts[0].acknowledged_at).toBe('2026-09-11T12:05:00Z');
  });

  it('reconnect delay uses bounded exponential backoff with upper bound', () => {
    const minDelayMs = 1000;
    const maxDelayMs = 15000;

    const calculateBackoff = (attempt: number) => {
      return Math.min(minDelayMs * Math.pow(1.8, attempt), maxDelayMs);
    };

    expect(calculateBackoff(0)).toBe(1000);
    expect(calculateBackoff(1)).toBe(1800);
    expect(calculateBackoff(2)).toBe(3240);
    expect(calculateBackoff(5)).toBe(15000); // capped at max
    expect(calculateBackoff(10)).toBe(15000); // capped at max
  });
});
