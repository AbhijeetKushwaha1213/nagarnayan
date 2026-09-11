/**
 * Nagar Nayan — Real-time Application Context
 *
 * Provides a unified application-level WebSocket connection, connection state,
 * and maintains real-time state synchronization using IDs as stable identity.
 */

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { wsService, type ConnectionStatus } from '@/services/websocket';
import type { Alert, UrbanEvent, WebSocketEnvelope } from '@/types/backend';

interface RealtimeContextValue {
  connectionStatus: ConnectionStatus;
  activeClients: number;
  lastMessage: WebSocketEnvelope | null;
  events: UrbanEvent[];
  alerts: Alert[];
  setEvents: React.Dispatch<React.SetStateAction<UrbanEvent[]>>;
  setAlerts: React.Dispatch<React.SetStateAction<Alert[]>>;
  reconnect: () => void;
}

const RealtimeContext = createContext<RealtimeContextValue | null>(null);

export function RealtimeProvider({ children }: { children: React.ReactNode }) {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  const [activeClients, setActiveClients] = useState<number>(0);
  const [lastMessage, setLastMessage] = useState<WebSocketEnvelope | null>(null);
  const [events, setEvents] = useState<UrbanEvent[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);

  useEffect(() => {
    // 1. Subscribe to connection status changes
    const unsubStatus = wsService.subscribeStatus((status) => {
      setConnectionStatus(status);
    });

    // 2. Subscribe to incoming messages with stable identity deduplication
    const unsubMessage = wsService.subscribe((envelope) => {
      setLastMessage(envelope);

      switch (envelope.type) {
        case 'system.connected': {
          if (envelope.data?.active_clients !== undefined) {
            setActiveClients(Number(envelope.data.active_clients));
          }
          break;
        }

        case 'event.created': {
          const newEvent = envelope.data as UrbanEvent;
          if (!newEvent?.id) break;
          setEvents((prev) => {
            const exists = prev.some((e) => e.id === newEvent.id);
            if (exists) {
              return prev.map((e) => (e.id === newEvent.id ? { ...e, ...newEvent } : e));
            }
            return [newEvent, ...prev];
          });
          break;
        }

        case 'event.updated': {
          const updatedEvent = envelope.data as UrbanEvent;
          if (!updatedEvent?.id) break;
          setEvents((prev) => {
            const exists = prev.some((e) => e.id === updatedEvent.id);
            if (exists) {
              return prev.map((e) => (e.id === updatedEvent.id ? { ...e, ...updatedEvent } : e));
            }
            return [updatedEvent, ...prev];
          });
          break;
        }

        case 'alert.created': {
          const newAlert = envelope.data as Alert;
          if (!newAlert?.id) break;
          setAlerts((prev) => {
            const exists = prev.some((a) => a.id === newAlert.id);
            if (exists) {
              return prev.map((a) => (a.id === newAlert.id ? { ...a, ...newAlert } : a));
            }
            return [newAlert, ...prev];
          });
          break;
        }

        case 'alert.updated': {
          const updatedAlert = envelope.data as Alert;
          if (!updatedAlert?.id) break;
          setAlerts((prev) => {
            const exists = prev.some((a) => a.id === updatedAlert.id);
            if (exists) {
              return prev.map((a) => (a.id === updatedAlert.id ? { ...a, ...updatedAlert } : a));
            }
            return [updatedAlert, ...prev];
          });
          break;
        }

        default:
          break;
      }
    });

    // 3. Connect application-level WebSocket
    wsService.connect();

    return () => {
      unsubStatus();
      unsubMessage();
      wsService.disconnect();
    };
  }, []);

  const reconnect = useCallback(() => {
    wsService.disconnect();
    wsService.connect();
  }, []);

  return (
    <RealtimeContext.Provider
      value={{
        connectionStatus,
        activeClients,
        lastMessage,
        events,
        alerts,
        setEvents,
        setAlerts,
        reconnect,
      }}
    >
      {children}
    </RealtimeContext.Provider>
  );
}

export function useRealtime(): RealtimeContextValue {
  const ctx = useContext(RealtimeContext);
  if (!ctx) {
    throw new Error('useRealtime must be used within a RealtimeProvider');
  }
  return ctx;
}
