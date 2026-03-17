"use client";

import { useEffect, useRef, useCallback } from "react";
import { SSE_EVENTS_URL } from "@/lib/api";

type EventHandler = (data: Record<string, unknown>) => void;

/**
 * React hook to subscribe to SSE events from the backend.
 * Automatically reconnects on disconnect and cleans up on unmount.
 *
 * @param handlers - Map of event type → handler function
 * @param enabled  - Whether the subscription is active
 */
export function useEventSource(
  handlers: Record<string, EventHandler>,
  enabled = true,
) {
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!enabled) return undefined;

    const es = new EventSource(SSE_EVENTS_URL);

    // Register listeners for each event type
    for (const eventType of Object.keys(handlersRef.current)) {
      es.addEventListener(eventType, (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data);
          handlersRef.current[eventType]?.(data);
        } catch {
          // Ignore malformed payloads
        }
      });
    }

    es.onerror = () => {
      es.close();
      // Reconnect after 5 seconds, but only if still mounted
      if (mountedRef.current) {
        reconnectTimer.current = setTimeout(() => connect(), 5000);
      }
    };

    return es;
  }, [enabled]);

  useEffect(() => {
    mountedRef.current = true;
    const es = connect();
    return () => {
      mountedRef.current = false;
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
      es?.close();
    };
  }, [connect]);
}
