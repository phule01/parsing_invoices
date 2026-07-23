import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useWebSocket } from '../context/WebSocketContext';
import InvoiceModule from '../components/InvoiceModule/InvoiceModule';
import ProductModule from '../components/ProductModule/ProductModule';
import SettingsModule from '../components/SettingsModule/SettingsModule';
import './Dashboard.css';

const MODULE_CRUMBS = {
  invoices: 'INVOICES',
  products: 'PRODUCTS',
  settings: 'SETTINGS & INTEGRATIONS',
};

function Dashboard() {
  const { user, logout } = useAuth();
  const { isConnected } = useWebSocket();
  const [activeModule, setActiveModule] = useState('invoices');

  return (
    <div id="view-app" className="view active">
      <div className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-brand-title">Invoice<br />Management</div>
          <div className="sidebar-brand-status">
            <span className={`dot ${isConnected ? 'live' : 'offline'}`}></span>
            {isConnected ? 'LIVE' : 'OFFLINE'}
          </div>
        </div>

        <div
          className={`nav-item ${activeModule === 'invoices' ? 'active' : ''}`}
          onClick={() => setActiveModule('invoices')}
        >
          <span className="nav-icon">▤</span> Invoices
        </div>

        <div
          className={`nav-item ${activeModule === 'products' ? 'active' : ''}`}
          onClick={() => setActiveModule('products')}
        >
          <span className="nav-icon">▣</span> Products
        </div>

        <div
          className={`nav-item ${activeModule === 'settings' ? 'active' : ''}`}
          onClick={() => setActiveModule('settings')}
        >
          <span className="nav-icon">⚙</span> Change Setting
        </div>
      </div>

      <div className="main">
        <div className="topbar">
          <div className="topbar-title">{MODULE_CRUMBS[activeModule] || 'DASHBOARD'}</div>
          <div className="topbar-right">
            <div className="welcome">
              Welcome, <b>{user?.username || 'User'}</b>
            </div>
            <button className="btn-ghost" onClick={logout}>
              Logout
            </button>
          </div>
        </div>

        <div className="content">
          {activeModule === 'invoices' && <InvoiceModule />}
          {activeModule === 'products' && <ProductModule />}
          {activeModule === 'settings' && <SettingsModule />}
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
