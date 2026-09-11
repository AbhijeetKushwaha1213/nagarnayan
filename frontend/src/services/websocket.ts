/**
 * Nagar Nayan — Real-time WebSocket Service
 *
 * Manages an application-level persistent WebSocket connection to /api/v1/ws.
 * Handles automatic reconnection with bounded exponential backoff, keepalive pings,
 * and broadcasts incoming message envelopes to subscribed listeners.
 */

import { ENV } from '@/config/env';
import type { WebSocketEnvelope } from '@/types/backend';

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected';

export type WebSocketMessageListener = (message: WebSocketEnvelope) => void;
export type ConnectionStatusListener = (status: ConnectionStatus) => void;

class RealtimeWebSocketService {
  private socket: WebSocket | null = null;
  private status: ConnectionStatus = 'disconnected';
  private reconnectAttempts = 0;
  private reconnectTimer: any = null;
  private heartbeatTimer: any = null;
  private isManuallyClosed = false;

  private messageListeners = new Set<WebSocketMessageListener>();
  private statusListeners = new Set<ConnectionStatusListener>();

  private readonly minDelayMs = 1000;
  private readonly maxDelayMs = 15000;
  private readonly heartbeatIntervalMs = 30000;

  constructor() {
    // Singleton instance
  }

  public getStatus(): ConnectionStatus {
    return this.status;
  }

  public connect(): void {
    if (this.socket && (this.status === 'connected' || this.status === 'connecting')) {
      return;
    }

    this.isManuallyClosed = false;
    this.setStatus('connecting');

    try {
      this.socket = new WebSocket(ENV.WS_URL);
    } catch (err) {
      console.warn('[WebSocket] Failed to instantiate WebSocket:', err);
      this.scheduleReconnect();
      return;
    }

    this.socket.onopen = () => {
      this.setStatus('connected');
      this.reconnectAttempts = 0;
      this.startHeartbeat();
    };

    this.socket.onmessage = (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data) as WebSocketEnvelope;
        this.notifyMessage(payload);
      } catch (err) {
        console.warn('[WebSocket] Received non-JSON message:', event.data);
      }
    };

    this.socket.onerror = (err: Event) => {
      console.warn('[WebSocket] Error encountered:', err);
      // Let onclose handle state transition and reconnection
    };

    this.socket.onclose = () => {
      this.stopHeartbeat();
      this.socket = null;
      this.setStatus('disconnected');

      if (!this.isManuallyClosed) {
        this.scheduleReconnect();
      }
    };
  }

  public disconnect(): void {
    this.isManuallyClosed = true;
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.socket) {
      this.socket.close(1000, 'Client closed connection');
      this.socket = null;
    }
    this.setStatus('disconnected');
  }

  public send(payload: Record<string, any> | string): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      const data = typeof payload === 'string' ? payload : JSON.stringify(payload);
      this.socket.send(data);
    }
  }

  public subscribe(listener: WebSocketMessageListener): () => void {
    this.messageListeners.add(listener);
    return () => {
      this.messageListeners.delete(listener);
    };
  }

  public subscribeStatus(listener: ConnectionStatusListener): () => void {
    this.statusListeners.add(listener);
    listener(this.status);
    return () => {
      this.statusListeners.delete(listener);
    };
  }

  private setStatus(newStatus: ConnectionStatus): void {
    if (this.status !== newStatus) {
      this.status = newStatus;
      for (const listener of this.statusListeners) {
        try {
          listener(newStatus);
        } catch (err) {
          console.error('[WebSocket] Error in status listener:', err);
        }
      }
    }
  }

  private notifyMessage(message: WebSocketEnvelope): void {
    for (const listener of this.messageListeners) {
      try {
        listener(message);
      } catch (err) {
        console.error('[WebSocket] Error in message listener:', err);
      }
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer || this.isManuallyClosed) return;

    // Bounded exponential backoff: min(1000 * 1.8^n, 15000) + jitter
    const backoff = Math.min(
      this.minDelayMs * Math.pow(1.8, this.reconnectAttempts),
      this.maxDelayMs,
    );
    const jitter = Math.random() * 500;
    const delay = Math.round(backoff + jitter);

    this.reconnectAttempts += 1;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.send({ type: 'ping' });
      }
    }, this.heartbeatIntervalMs);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }
}

export const wsService = new RealtimeWebSocketService();
