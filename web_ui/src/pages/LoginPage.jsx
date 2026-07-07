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
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const [adminForm, setAdminForm] = useState({
    username: '',
    password: '',
    telegram_bot_token: '',
    telegram_chat_id: '',
  });

  // User Register Form
  const [registerForm, setRegisterForm] = useState({
    username: '',
    password: '',
  });
  const [successMessage, setSuccessMessage] = useState('');

  // Check if admin exists
  useEffect(() => {
    const checkAdmin = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/auth/has-admin`);
        if (response.ok) {
          const data = await response.json();
          setAdminExists(data.has_admin);
        } else {
          setAdminExists(false);
        }
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
    if (!adminForm.username || !adminForm.password) {
      setLocalError('Username and password are required');
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/api/auth/admin-setup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: adminForm.username,
          password: adminForm.password,
          telegram_bot_token: adminForm.telegram_bot_token,
          telegram_chat_id: adminForm.telegram_chat_id,
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

  // Handle user registration
  const handleRegister = async (e) => {
    e.preventDefault();
    setLocalError('');
    setSuccessMessage('');

    if (!registerForm.username || !registerForm.password) {
      setLocalError('Username and password are required');
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/api/auth/public-register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: registerForm.username,
          password: registerForm.password,
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Registration failed');
      }
      
      setSuccessMessage('Your account has been created. Please wait for the Admin to approve your access before logging in.');
      setRegisterForm({ username: '', password: '' });
    } catch (err) {
      setLocalError(err.message || 'Registration failed. Please try again.');
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
            {adminExists ? (
              <>
                <button
                  className={`tab-button ${activeTab === 'user' ? 'active' : ''}`}
                  onClick={() => setActiveTab('user')}
                >
                  👤 Login
                </button>
                <button
                  className={`tab-button ${activeTab === 'register' ? 'active' : ''}`}
                  onClick={() => setActiveTab('register')}
                >
                  📝 Create Account
                </button>
              </>
            ) : (
              <button
                className={`tab-button ${activeTab === 'admin' ? 'active' : ''}`}
                onClick={() => setActiveTab('admin')}
              >
                🔧 Admin Setup
              </button>
            )}
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

          {/* Register Tab */}
          {activeTab === 'register' && (
            <form onSubmit={handleRegister}>
              <div className="form-group">
                <label htmlFor="reg_username">Username</label>
                <input
                  id="reg_username"
                  type="text"
                  value={registerForm.username}
                  onChange={(e) => setRegisterForm({ ...registerForm, username: e.target.value })}
                  placeholder="Choose a username"
                  disabled={loading}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="reg_password">Password</label>
                <input
                  id="reg_password"
                  type="password"
                  value={registerForm.password}
                  onChange={(e) => setRegisterForm({ ...registerForm, password: e.target.value })}
                  placeholder="Create a strong password"
                  disabled={loading}
                  required
                />
              </div>

              {(error || localError) && (
                <div className="error-message">{error || localError}</div>
              )}
              {successMessage && (
                <div className="success-message" style={{ color: 'green', marginBottom: '15px' }}>
                  {successMessage}
                </div>
              )}

              <button type="submit" disabled={loading} className="login-button">
                {loading ? 'Creating Account...' : 'Create Account'}
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
        </div>
      </div>
    </div>
  );
}

export default LoginPage;
