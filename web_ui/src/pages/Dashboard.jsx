import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useWebSocket } from '../context/WebSocketContext';
import InvoiceModule from '../components/InvoiceModule/InvoiceModule';
import ProductModule from '../components/ProductModule/ProductModule';
import SettingsModule from '../components/SettingsModule/SettingsModule';
import './Dashboard.css';

function Dashboard() {
  const { user, logout } = useAuth();
  const { isConnected } = useWebSocket();
  const [activeModule, setActiveModule] = useState('invoices');

  return (
    <div className="dashboard">
      <nav className="navbar">
        <div className="navbar-header">
          <h1>Invoice Management System</h1>
          <div className="navbar-status">
            <span className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`}></span>
            <span className="status-text">{isConnected ? 'Live' : 'Offline'}</span>
          </div>
        </div>

        <div className="navbar-user">
          <span className="user-info">Welcome, <strong>{user?.username}</strong></span>
          <button onClick={logout} className="logout-button">Logout</button>
        </div>
      </nav>

      <div className="dashboard-container">
        <aside className="sidebar">
          <nav className="sidebar-nav">
            <button
              className={`nav-item ${activeModule === 'invoices' ? 'active' : ''}`}
              onClick={() => setActiveModule('invoices')}
            >
              📄 Invoices
            </button>
            <button
              className={`nav-item ${activeModule === 'products' ? 'active' : ''}`}
              onClick={() => setActiveModule('products')}
            >
              📦 Products
            </button>
            <button
              className={`nav-item ${activeModule === 'settings' ? 'active' : ''}`}
              onClick={() => setActiveModule('settings')}
            >
              ⚙️ Change Setting
            </button>
          </nav>
        </aside>

        <main className="dashboard-content">
          {activeModule === 'invoices' && <InvoiceModule />}
          {activeModule === 'products' && <ProductModule />}
          {activeModule === 'settings' && <SettingsModule />}
        </main>
      </div>
    </div>
  );
}

export default Dashboard;
