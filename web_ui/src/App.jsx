import React from 'react';
import './App.css';
import LoginPage from './pages/LoginPage';
import Dashboard from './pages/Dashboard';
import NotificationCenter from './components/NotificationCenter/NotificationCenter';
import { AuthProvider, useAuth } from './context/AuthContext';
import { WebSocketProvider } from './context/WebSocketContext';

function AppContent() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading-container">
        <div className="spinner"></div>
        <p>Loading...</p>
      </div>
    );
  }

  return (
    <>
      <NotificationCenter />
      {user ? <Dashboard /> : <LoginPage />}
    </>
  );
}

function App() {
  return (
    <AuthProvider>
      <WebSocketProvider>
        <AppContent />
      </WebSocketProvider>
    </AuthProvider>
  );
}

export default App;
