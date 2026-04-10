import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * useWebSocket: A specialized React hook for real-time GRC telemetry.
 * Features: Exponential backoff reconnection and decoupled auth state.
 */
export const useWebSocket = (token, onMessage) => {
    const [connected, setConnected] = useState(false);
    const [retryCount, setRetryCount] = useState(0);
    const socketRef = useRef(null);
    const onMessageRef = useRef(onMessage);

    useEffect(() => {
        onMessageRef.current = onMessage;
    }, [onMessage]);

    const connect = useCallback(() => {
        if (!token) return;

        // Cleanup existing connection before reconnecting
        if (socketRef.current) {
            socketRef.current.close();
        }

        const wsBaseUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8001';
        const wsUrl = `${wsBaseUrl}/api/v1/stream?token=${token}`;
        
        console.log("WebSocket_Init: Establishing secure telemetry stream...");
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log("WebSocket_Sync: Connection Synchronized.");
            setConnected(true);
            setRetryCount(0);
        };

        ws.onmessage = (event) => {
            try {
                const payload = JSON.parse(event.data);
                if (onMessageRef.current) onMessageRef.current(payload);
            } catch (err) {
                console.error("WebSocket_Error: Payload parse failure", err);
            }
        };

        ws.onclose = (event) => {
            setConnected(false);
            
            // Do not reconnect on policy violations or manual closures
            if (event.code === 1008 || event.code === 1000) {
                console.warn("WebSocket_Auth: Policy violation or intentional closure.");
                return;
            }

            // Exponential Backoff Reconnection (Rule #3)
            const timeout = Math.min(1000 * Math.pow(2, retryCount), 30000);
            console.log(`WebSocket_Retry: Reconnecting in ${timeout}ms...`);
            
            setTimeout(() => {
                setRetryCount(prev => prev + 1);
            }, timeout);
        };

        ws.onerror = () => {
            console.error("WebSocket_Fault: Connection error detected.");
            ws.close();
        };

        socketRef.current = ws;
    }, [token, retryCount]);

    useEffect(() => {
        connect();
        return () => {
            if (socketRef.current) {
                socketRef.current.close(1000, "Component Unmounting");
            }
        };
    }, [connect]);

    return { connected };
};
