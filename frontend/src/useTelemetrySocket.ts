import { useEffect, useRef, useState } from 'react';
import { TelemetryFrame } from './types';

export function useTelemetrySocket() {
  const [currentFrame, setCurrentFrame] = useState<TelemetryFrame | null>(null);
  const [history, setHistory] = useState<TelemetryFrame[]>([]);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [latencyMs, setLatencyMs] = useState<number>(0);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastFingerprintRef = useRef<string>('');

  useEffect(() => {
    let unmounted = false;

    function connect() {
      if (unmounted) return;

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/telemetry`;

      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      const sendTimeRef = { current: performance.now() };

      ws.onopen = () => {
        if (unmounted) return;
        setIsConnected(true);
        console.log('[WebSocket] Connected to live industrial telemetry stream.');
      };

      ws.onmessage = (event) => {
        if (unmounted) return;
        const now = performance.now();
        const delta = Math.round(now - sendTimeRef.current);
        sendTimeRef.current = now;

        try {
          const frame: TelemetryFrame = JSON.parse(event.data);
          const fingerprint = `${frame.run_id}:${frame.step}:${frame.model_mode}:${frame.risk_score}:${frame.regime}`;
          
          setLatencyMs(frame.inference_latency_ms || delta);

          // If frame state is identical to last processed frame, prevent React re-render storm
          if (fingerprint === lastFingerprintRef.current) {
            return;
          }
          lastFingerprintRef.current = fingerprint;

          setCurrentFrame(frame);

          setHistory((prev) => {
            if (prev.length === 0) return [frame];

            const last = prev[prev.length - 1];

            // 1. If run_id changed or user scrubbed backward, reset history cleanly
            if (last.run_id !== frame.run_id || frame.step < last.step) {
              return [frame];
            }

            // 2. If paused at the same step, update last frame in place without adding duplicate points
            if (last.step === frame.step) {
              const updated = [...prev];
              updated[updated.length - 1] = frame;
              return updated;
            }

            // 3. Advancing step: append new frame and keep trailing window of max 120 points
            const next = [...prev, frame];
            if (next.length > 120) next.shift();
            return next;
          });
        } catch (err) {
          console.error('[WebSocket] Failed to parse telemetry frame:', err);
        }
      };

      ws.onclose = () => {
        if (unmounted) return;
        setIsConnected(false);
        console.log('[WebSocket] Disconnected. Reconnecting in 2s...');
        reconnectTimeoutRef.current = setTimeout(connect, 2000);
      };

      ws.onerror = (err) => {
        console.warn('[WebSocket] Encountered connection error:', err);
        ws.close();
      };
    }

    connect();

    return () => {
      unmounted = true;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (socketRef.current) socketRef.current.close();
    };
  }, []);

  return { currentFrame, history, isConnected, latencyMs };
}
