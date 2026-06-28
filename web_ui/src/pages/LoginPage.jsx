import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import './LoginPage.css';

const API_BASE = process.env.REACT_APP_API_URL || (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : '');

function LoginPage() {
  const { login, loading, error } = useAuth();
  const [activeTab, setActiveTab] = useState('user'); // 'user' or 'admin'
  const [adminExists, setAdminExists] = useState(false);
  const [localError, setLocalError] = useState('');

  // User Login Form
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin');

  // Admin Setup Form
  const [adminForm, setAdminForm] = useState({
    username: '',
    email: '',
    password: '',
    email_address: '',
    email_password: '',
    gemini_api_key: '',
    telegram_bot_token: '',
    telegram_chat_id: '',
    imap_server: 'imap.gmail.com',
    smtp_server: 'smtp.gmail.com',
  });

  // Check if admin exists
  useEffect(() => {
    const checkAdmin = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/auth/validate-token`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        });
        // If we can reach the API, we assume admin might exist (simplified check)
        setAdminExists(false); // Start with false, let backend handle the error
      } catch (err) {
        setAdminExists(false);
      }
    };
    checkAdmin();
  }, []);

  // Handle user login
  const handleUserLogin = async (e) => {
    e.preventDefault();
    setLocalError('');
    try {
      await login(username, password);
    } catch (err) {
      setLocalError(err.message || 'Login failed. Please try again.');
    }
  };

  // Handle admin setup
  const handleAdminSetup = async (e) => {
    e.preventDefault();
    setLocalError('');

    // Validate required fields
    if (!adminForm.username || !adminForm.email || !adminForm.password) {
      setLocalError('Username, email, and password are required');
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/api/auth/admin-setup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: adminForm.username,
          email: adminForm.email,
          password: adminForm.password,
          email_address: adminForm.email_address,
          email_password: adminForm.email_password,
          gemini_api_key: adminForm.gemini_api_key,
          telegram_bot_token: adminForm.telegram_bot_token,
          telegram_chat_id: adminForm.telegram_chat_id,
          imap_server: adminForm.imap_server,
          smtp_server: adminForm.smtp_server,
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Admin setup failed');
      }

      const data = await response.json();
      // Store token and login
      localStorage.setItem('token', data.access_token);
      localStorage.setItem('user_id', data.user_id);
      localStorage.setItem('username', data.username);
      window.location.href = '/';
    } catch (err) {
      setLocalError(err.message || 'Admin setup failed');
    }
  };

  // Handle admin form changes
  const handleAdminFormChange = (e) => {
    const { name, value } = e.target;
    setAdminForm(prev => ({ ...prev, [name]: value }));
  };

  return (
    <div className="login-page">
      <div className="login-container">
        <div className="login-box">
          <h1>Invoice Management System</h1>
          <p className="subtitle">Dashboard & Telegram Bot Integration</p>

          {/* Tabs */}
          <div className="login-tabs">
            <button
              className={`tab-button ${activeTab === 'user' ? 'active' : ''}`}
              onClick={() => setActiveTab('user')}
            >
              👤 User Login
            </button>
            <button
              className={`tab-button ${activeTab === 'admin' ? 'active' : ''}`}
              onClick={() => setActiveTab('admin')}
            >
              🔧 Admin Setup
            </button>
          </div>

          {/* User Login Tab */}
          {activeTab === 'user' && (
            <form onSubmit={handleUserLogin}>
              <div className="form-group">
                <label htmlFor="username">Username</label>
                <input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter your username"
                  disabled={loading}
                  autoFocus
                />
              </div>

              <div className="form-group">
                <label htmlFor="password">Password</label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  disabled={loading}
                />
              </div>

              {(error || localError) && (
                <div className="error-message">{error || localError}</div>
              )}

              <button type="submit" disabled={loading} className="login-button">
                {loading ? 'Logging in...' : 'Login'}
              </button>
            </form>
          )}

          {/* Admin Setup Tab */}
          {activeTab === 'admin' && (
            <form onSubmit={handleAdminSetup}>
              <p className="admin-subtitle">One-time system configuration</p>

              {/* Basic Info Section */}
              <fieldset className="form-section">
                <legend>Basic Account Information</legend>
                
                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="admin_username">Username</label>
                    <input
                      id="admin_username"
                      type="text"
                      name="username"
                      value={adminForm.username}
                      onChange={handleAdminFormChange}
                      placeholder="Admin username"
                      disabled={loading}
                      autoFocus
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="admin_email">Email</label>
                    <input
                      id="admin_email"
                      type="email"
                      name="email"
                      value={adminForm.email}
                      onChange={handleAdminFormChange}
                      placeholder="admin@example.com"
                      disabled={loading}
                      required
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label htmlFor="admin_password">Password</label>
                  <input
                    id="admin_password"
                    type="password"
                    name="password"
                    value={adminForm.password}
                    onChange={handleAdminFormChange}
                    placeholder="Create a strong password"
                    disabled={loading}
                    required
                  />
                </div>
              </fieldset>

              {/* Email Configuration Section */}
              <fieldset className="form-section">
                <legend>Email Configuration</legend>

                <div className="form-group">
                  <label htmlFor="email_address">Email Address (Gmail)</label>
                  <input
                    id="email_address"
                    type="email"
                    name="email_address"
                    value={adminForm.email_address}
                    onChange={handleAdminFormChange}
                    placeholder="your.email@gmail.com"
                    disabled={loading}
                    required
                  />
                  <small>The Gmail address to send invoices from</small>
                </div>

                <div className="form-group">
                  <label htmlFor="email_password">Gmail App Password</label>
                  <input
                    id="email_password"
                    type="password"
                    name="email_password"
                    value={adminForm.email_password}
                    onChange={handleAdminFormChange}
                    placeholder="16-character app password"
                    disabled={loading}
                    required
                  />
                  <small>
                    ⚠️ Use <a href="https://support.google.com/accounts/answer/185833" target="_blank" rel="noopener noreferrer">Gmail App Password</a>, not your regular password. Enable 2FA first.
                  </small>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="imap_server">IMAP Server</label>
                    <input
                      id="imap_server"
                      type="text"
                      name="imap_server"
                      value={adminForm.imap_server}
                      onChange={handleAdminFormChange}
                      placeholder="imap.gmail.com"
                      disabled={loading}
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="smtp_server">SMTP Server</label>
                    <input
                      id="smtp_server"
                      type="text"
                      name="smtp_server"
                      value={adminForm.smtp_server}
                      onChange={handleAdminFormChange}
                      placeholder="smtp.gmail.com"
                      disabled={loading}
                    />
                  </div>
                </div>
              </fieldset>

              {/* AI Parser Configuration Section */}
              <fieldset className="form-section">
                <legend>AI Parser (Invoice Extraction)</legend>

                <div className="form-group">
                  <label htmlFor="gemini_api_key">Google Gemini API Key</label>
                  <input
                    id="gemini_api_key"
                    type="password"
                    name="gemini_api_key"
                    value={adminForm.gemini_api_key}
                    onChange={handleAdminFormChange}
                    placeholder="Your API key"
                    disabled={loading}
                    required
                  />
                  <small>
                    Get it from <a href="https://ai.google.dev" target="_blank" rel="noopener noreferrer">Google AI Studio</a>
                  </small>
                </div>
              </fieldset>

              {/* Telegram Configuration Section */}
              <fieldset className="form-section">
                <legend>Telegram Bot Integration</legend>

                <div className="form-group">
                  <label htmlFor="telegram_bot_token">Telegram Bot Token</label>
                  <input
                    id="telegram_bot_token"
                    type="password"
                    name="telegram_bot_token"
                    value={adminForm.telegram_bot_token}
                    onChange={handleAdminFormChange}
                    placeholder="Your bot token from BotFather"
                    disabled={loading}
                    required
                  />
                  <small>
                    Create a bot with <a href="https://t.me/botfather" target="_blank" rel="noopener noreferrer">BotFather</a>
                  </small>
                </div>

                <div className="form-group">
                  <label htmlFor="telegram_chat_id">Telegram Chat ID</label>
                  <input
                    id="telegram_chat_id"
                    type="text"
                    name="telegram_chat_id"
                    value={adminForm.telegram_chat_id}
                    onChange={handleAdminFormChange}
                    placeholder="Your chat ID"
                    disabled={loading}
                    required
                  />
                  <small>
                    Send /start to <a href="https://t.me/userinfobot" target="_blank" rel="noopener noreferrer">@userinfobot</a> to get your ID
                  </small>
                </div>
              </fieldset>

              {(error || localError) && (
                <div className="error-message">{error || localError}</div>
              )}

              <button type="submit" disabled={loading} className="login-button">
                {loading ? 'Setting up...' : 'Complete Admin Setup'}
              </button>
            </form>
          )}

          {activeTab === 'user' && (
            <div className="demo-info">
              <h3>Demo Credentials:</h3>
              <p><strong>Username:</strong> admin</p>
              <p><strong>Password:</strong> admin</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default LoginPage;
