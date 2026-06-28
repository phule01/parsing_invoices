import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { useAuth } from './AuthContext';

const WebSocketContext = createContext(null);

export function WebSocketProvider({ children }) {
  const { token, user } = useAuth();
  const [ws, setWs] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [listeners, setListeners] = useState({});

  // Connect WebSocket when token is available
  useEffect(() => {
    if (!token || !user) return;

    const connectWebSocket = () => {
      try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        let wsUrl = `${protocol}//${window.location.host}/api/ws/updates?token=${token}`;
        
        if (process.env.REACT_APP_API_URL) {
           const baseUrl = process.env.REACT_APP_API_URL.replace(/^http/, 'ws');
           wsUrl = `${baseUrl}/api/ws/updates?token=${token}`;
        } else if (process.env.NODE_ENV === 'development') {
           wsUrl = `ws://localhost:8000/api/ws/updates?token=${token}`;
        }
        const websocket = new WebSocket(wsUrl);

        websocket.onopen = () => {
          console.log('WebSocket connected');
          setIsConnected(true);
        };

        websocket.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            console.log('WebSocket message:', message);
            
            // Notify all listeners
            if (listeners[message.type]) {
              listeners[message.type].forEach(callback => callback(message));
            }
            
            // Notify all listeners
            if (listeners['*']) {
              listeners['*'].forEach(callback => callback(message));
            }
          } catch (err) {
            console.error('Error parsing WebSocket message:', err);
          }
        };

        websocket.onerror = (error) => {
          console.error('WebSocket error:', error);
          setIsConnected(false);
        };

        websocket.onclose = () => {
          console.log('WebSocket disconnected');
          setIsConnected(false);
          
          // Try to reconnect after 5 seconds
          setTimeout(connectWebSocket, 5000);
        };

        setWs(websocket);
      } catch (err) {
        console.error('Error connecting WebSocket:', err);
      }
    };

    connectWebSocket();

    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, [token, user]);

  // Subscribe to WebSocket events
  const subscribe = useCallback((eventType, callback) => {
    setListeners(prev => ({
      ...prev,
      [eventType]: [...(prev[eventType] || []), callback]
    }));

    // Return unsubscribe function
    return () => {
      setListeners(prev => ({
        ...prev,
        [eventType]: (prev[eventType] || []).filter(cb => cb !== callback)
      }));
    };
  }, []);

  // Send message via WebSocket
  const send = useCallback((message) => {
    if (ws && isConnected) {
      ws.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected');
    }
  }, [ws, isConnected]);

  const value = {
    ws,
    isConnected,
    subscribe,
    send
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocket() {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within WebSocketProvider');
  }
  return context;
}
