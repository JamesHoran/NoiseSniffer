import { useEffect, useRef, useState, useCallback } from 'react';

// Types for WebSocket messages
export interface SpectrumMessage {
  type: 'spectrum';
  bins: number[]; // 0.0 to 1.0 range
  annotations?: Array<{
    label: string;
    frequency: number;
  }>;
}

export interface PacketMessage {
  type: 'packet';
  timestamp: string;
  src_ip: string;
  dst_ip: string;
  src_port: number;
  dst_port: number;
  protocol: string;
  flags?: string;
  length: number;
  packet_type: 'normal' | 'suspicious' | 'malicious';
}

export type WebSocketMessage = SpectrumMessage | PacketMessage;

export interface UseWebSocketOptions<T extends WebSocketMessage = WebSocketMessage> {
  onMessage?: (message: T) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  reconnectInterval?: number;
  reconnectAttempts?: number;
}

export interface UseWebSocketReturn<T extends WebSocketMessage = WebSocketMessage> {
  isConnected: boolean;
  lastMessage: T | null;
  sendMessage: (message: string) => void;
  connect: () => void;
  disconnect: () => void;
}

/**
 * React hook for managing WebSocket connections with auto-reconnect.
 */
export function useWebSocket<T extends WebSocketMessage = WebSocketMessage>(
  url: string,
  options: UseWebSocketOptions<T> = {}
): UseWebSocketReturn<T> {
  const {
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    reconnectInterval = 3000,
    reconnectAttempts = 5,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<T | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const isManualCloseRef = useRef(false);
  const onMessageRef = useRef(onMessage);
  const onConnectRef = useRef(onConnect);
  const onDisconnectRef = useRef(onDisconnect);
  const onErrorRef = useRef(onError);

  // Keep callback refs in sync
  useEffect(() => {
    onMessageRef.current = onMessage;
    onConnectRef.current = onConnect;
    onDisconnectRef.current = onDisconnect;
    onErrorRef.current = onError;
  }, [onMessage, onConnect, onDisconnect, onError]);

  // Parse JSON message safely
  const parseMessage = useCallback((data: string): T | null => {
    try {
      return JSON.parse(data) as T;
    } catch {
      console.error('Failed to parse WebSocket message:', data);
      return null;
    }
  }, []);

  // Clean up connection
  const cleanup = useCallback(() => {
    if (reconnectTimeoutRef.current !== null) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  // Connect to WebSocket
  const connect = useCallback(() => {
    // Clear any existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;
        onConnectRef.current?.();
      };

      ws.onmessage = (event) => {
        const message = parseMessage(event.data);
        if (message) {
          setLastMessage(message);
          onMessageRef.current?.(message);
        }
      };

      ws.onerror = (error) => {
        onErrorRef.current?.(error);
      };

      ws.onclose = () => {
        setIsConnected(false);
        onDisconnectRef.current?.();

        // Auto-reconnect if not manually closed
        if (!isManualCloseRef.current && reconnectAttemptsRef.current < reconnectAttempts) {
          reconnectAttemptsRef.current++;
          reconnectTimeoutRef.current = window.setTimeout(() => {
            // Reconnect using the same logic
            if (wsRef.current === null) { // Only reconnect if not already connected
              // eslint-disable-next-line react-hooks/immutability -- Auto-reconnect requires self-reference
              connect();
            }
          }, reconnectInterval);
        } else if (isManualCloseRef.current) {
          isManualCloseRef.current = false;
        }
      };
    } catch (error) {
      console.error('WebSocket connection error:', error);
      onErrorRef.current?.(error as Event);
    }
  }, [url, reconnectInterval, reconnectAttempts, parseMessage]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    isManualCloseRef.current = true;
    cleanup();
  }, [cleanup]);

  // Send message to WebSocket
  const sendMessage = useCallback((message: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(message);
    } else {
      console.warn('WebSocket is not connected. Cannot send message:', message);
    }
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    connect();
    return () => {
      cleanup();
    };
  }, [connect, cleanup]);

  return {
    isConnected,
    lastMessage,
    sendMessage,
    connect,
    disconnect,
  };
}
