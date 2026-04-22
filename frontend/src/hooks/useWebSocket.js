/**
 * useWebSocket hook — real-time job progress via WebSocket
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import { API_BASE } from '../utils/api';

export function useWebSocket(jobId) {
  const [data, setData] = useState(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  const connect = useCallback(() => {
    const token = localStorage.getItem('token');
    let wsBase;
    if (API_BASE && API_BASE.startsWith('http')) {
      wsBase = API_BASE.replace('http', 'ws');
    } else {
      // Derive from current page location (production mode through Nginx)
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      wsBase = `${proto}//${window.location.host}`;
    }
    const url = jobId
      ? `${wsBase}/ws/jobs/${jobId}?token=${token}`
      : `${wsBase}/ws/dashboard?token=${token}`;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        // Start ping interval
        const pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, 30000);
        ws._pingInterval = pingInterval;
      };

      ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          if (parsed.type !== 'pong') {
            setData(parsed);
          }
        } catch (e) {
          console.error('WS parse error:', e);
        }
      };

      ws.onclose = () => {
        setConnected(false);
        if (ws._pingInterval) clearInterval(ws._pingInterval);
        // Auto-reconnect after 3s
        reconnectTimer.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch (e) {
      console.error('WS connection error:', e);
    }
  }, [jobId]);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
      }
    };
  }, [connect]);

  return { data, connected };
}
