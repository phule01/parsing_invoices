import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import './SettingsModule.css';

const API_BASE = process.env.REACT_APP_API_URL || (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : '');

function SettingsModule() {
  const { token, user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [testInProgress, setTestInProgress] = useState('');
  
  // User Management State
  const [newUser, setNewUser] = useState({ username: '', email: '', password: '' });
  const [userLoading, setUserLoading] = useState(false);
  const [userSuccess, setUserSuccess] = useState('');
  const [userError, setUserError] = useState('');

  const [settings, setSettings] = useState({
    EMAIL_ADDRESS: '',
    EMAIL_PASSWORD: '',
    GEMINI_API_KEY: '',
    TELEGRAM_BOT_TOKEN: '',
    TELEGRAM_CHAT_ID: '',
    IMAP_SERVER: '',
    SMTP_SERVER: '',
  });

  // Fetch current settings
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/settings/`, {
          headers: { Authorization: `Bearer ${token}` }
        });

        if (!response.ok) throw new Error('Failed to fetch settings');

        const data = await response.json();
        setSettings(data);
      } catch (err) {
        setError(err.message);
      }
    };

    if (token) {
      fetchSettings();
    }
  }, [token]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setSettings({ ...settings, [name]: value });
    setError('');
    setSuccess('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await fetch(`${API_BASE}/api/settings/update`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings),
      });

      if (!response.ok) throw new Error('Failed to update settings');

      const data = await response.json();
      setSuccess('✅ Settings updated successfully!');
      setTimeout(() => setSuccess(''), 5000);
    } catch (err) {
      setError(`❌ Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleTestEmail = async () => {
    if (!settings.EMAIL_ADDRESS) {
      setError('Please enter an email address to test');
      return;
    }

    setTestInProgress('email');
    setError('');

    try {
      const response = await fetch(`${API_BASE}/api/settings/test-email`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          target_email: settings.EMAIL_ADDRESS,
          email_address: settings.EMAIL_ADDRESS,
          email_password: settings.EMAIL_PASSWORD || '',
          smtp_server: settings.SMTP_SERVER || 'smtp.gmail.com'
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to send test email');
      }

      const data = await response.json();
      setSuccess(`✅ ${data.message}`);
      setTimeout(() => setSuccess(''), 5000);
    } catch (err) {
      setError(`❌ Error: ${err.message}`);
    } finally {
      setTestInProgress('');
    }
  };

  const handleTestTelegram = async () => {
    if (!settings.TELEGRAM_BOT_TOKEN || !settings.TELEGRAM_CHAT_ID) {
      setError('Please set both Telegram bot token and chat ID');
      return;
    }

    setTestInProgress('telegram');
    setError('');

    try {
      const response = await fetch(`${API_BASE}/api/settings/test-telegram`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          bot_token: settings.TELEGRAM_BOT_TOKEN,
          chat_id: settings.TELEGRAM_CHAT_ID
        })
      });

      if (!response.ok) throw new Error('Failed to send test message');

      const data = await response.json();
      if (data.status === 'error') {
        throw new Error(data.message);
      }
      setSuccess(`✅ ${data.message}`);
      setTimeout(() => setSuccess(''), 5000);
    } catch (err) {
      setError(`❌ Error: ${err.message}`);
    } finally {
      setTestInProgress('');
    }
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setUserLoading(true);
    setUserError('');
    setUserSuccess('');

    try {
      const response = await fetch(`${API_BASE}/api/auth/register`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(newUser),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to create user');
      }

      setUserSuccess(`✅ User ${newUser.username} created successfully!`);
      setNewUser({ username: '', email: '', password: '' });
      setTimeout(() => setUserSuccess(''), 5000);
    } catch (err) {
      setUserError(`❌ Error: ${err.message}`);
    } finally {
      setUserLoading(false);
    }
  };

  if (!user?.is_admin) {
    return (
      <div className="settings-module">
        <h2>ℹ️ System Information</h2>
        <p>👤 Standard users have read-only access to basic system info.</p>

        <div className="settings-info">
          <h3>System Email Configuration</h3>
          <p>
            <strong>Email Address:</strong> {settings.EMAIL_ADDRESS || 'Not configured'}
          </p>
          <p>
            <strong>IMAP Server:</strong> {settings.IMAP_SERVER || 'Not configured'}
          </p>
          <p>
            <strong>SMTP Server:</strong> {settings.SMTP_SERVER || 'Not configured'}
          </p>
        </div>
        
        <div className="settings-info" style={{marginTop: '20px'}}>
          <h3>⚠️ Access Restricted</h3>
          <p>System settings (API keys, bot tokens, app passwords) and User Management can only be modified by administrators. Please contact an admin if you need these details updated.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="settings-module">
      <h2>⚙️ Change Setting</h2>
      <p className="admin-only">👤 Admin only - Configure system integrations</p>

      {error && <div className="error-message">{error}</div>}
      {success && <div className="success-message">{success}</div>}

      <form onSubmit={handleSubmit} className="settings-form">
        {/* Email Configuration */}
        <fieldset className="settings-section">
          <legend>📧 Email Configuration (Gmail)</legend>

          <div className="form-group">
            <label htmlFor="EMAIL_ADDRESS">Sender Email Address</label>
            <input
              id="EMAIL_ADDRESS"
              type="email"
              name="EMAIL_ADDRESS"
              value={settings.EMAIL_ADDRESS}
              onChange={handleChange}
              placeholder="your-email@gmail.com"
            />
            <small>Email to send invoices from</small>
          </div>

          <div className="form-group">
            <label htmlFor="EMAIL_PASSWORD">Email App Password</label>
            <input
              id="EMAIL_PASSWORD"
              type="password"
              name="EMAIL_PASSWORD"
              value={settings.EMAIL_PASSWORD}
              onChange={handleChange}
              placeholder="••••••••••••••••"
            />
            <small>
              📝 Use{' '}
              <a href="https://support.google.com/accounts/answer/185833" target="_blank" rel="noopener noreferrer">
                Gmail App Password
              </a>
              , not your regular password
            </small>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="SMTP_SERVER">SMTP Server</label>
              <input
                id="SMTP_SERVER"
                type="text"
                name="SMTP_SERVER"
                value={settings.SMTP_SERVER}
                onChange={handleChange}
                placeholder="smtp.gmail.com"
              />
            </div>
          </div>

          <button
            type="button"
            onClick={handleTestEmail}
            disabled={testInProgress === 'email'}
            className="btn-test"
          >
            {testInProgress === 'email' ? '⏳ Testing...' : '🧪 Test Email'}
          </button>
        </fieldset>

        {/* IMAP Configuration */}
        <fieldset className="settings-section">
          <legend>📥 Email Listener Configuration (IMAP)</legend>

          <div className="form-group">
            <label htmlFor="IMAP_SERVER">IMAP Server</label>
            <input
              id="IMAP_SERVER"
              type="text"
              name="IMAP_SERVER"
              value={settings.IMAP_SERVER}
              onChange={handleChange}
              placeholder="imap.gmail.com"
            />
            <small>Server to receive and monitor invoices</small>
          </div>
        </fieldset>

        {/* AI Configuration */}
        <fieldset className="settings-section">
          <legend>🤖 AI Parser Configuration (Google Gemini)</legend>

          <div className="form-group">
            <label htmlFor="GEMINI_API_KEY">Gemini API Key</label>
            <input
              id="GEMINI_API_KEY"
              type="password"
              name="GEMINI_API_KEY"
              value={settings.GEMINI_API_KEY}
              onChange={handleChange}
              placeholder="••••••••••••••••••••••••••••"
            />
            <small>
              Get key from{' '}
              <a href="https://ai.google.dev" target="_blank" rel="noopener noreferrer">
                Google AI Studio
              </a>
            </small>
          </div>
        </fieldset>

        {/* Telegram Configuration */}
        <fieldset className="settings-section">
          <legend>🤖 Telegram Bot Configuration</legend>

          <div className="form-group">
            <label htmlFor="TELEGRAM_BOT_TOKEN">Bot Token</label>
            <input
              id="TELEGRAM_BOT_TOKEN"
              type="password"
              name="TELEGRAM_BOT_TOKEN"
              value={settings.TELEGRAM_BOT_TOKEN}
              onChange={handleChange}
              placeholder="••••••••••••••••••••••••••••••••••••••"
            />
            <small>
              Get from{' '}
              <a href="https://t.me/botfather" target="_blank" rel="noopener noreferrer">
                @BotFather on Telegram
              </a>
            </small>
          </div>

          <div className="form-group">
            <label htmlFor="TELEGRAM_CHAT_ID">Chat ID</label>
            <input
              id="TELEGRAM_CHAT_ID"
              type="text"
              name="TELEGRAM_CHAT_ID"
              value={settings.TELEGRAM_CHAT_ID}
              onChange={handleChange}
              placeholder="123456789"
            />
            <small>Your Telegram chat ID (for receiving notifications)</small>
          </div>

          <button
            type="button"
            onClick={handleTestTelegram}
            disabled={testInProgress === 'telegram'}
            className="btn-test"
          >
            {testInProgress === 'telegram' ? '⏳ Testing...' : '🧪 Test Telegram'}
          </button>
        </fieldset>

        {/* Submit Button */}
        <div className="form-actions">
          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? '⏳ Saving...' : '💾 Save Settings'}
          </button>
        </div>
      </form>

      <div className="settings-info">
        <h3>ℹ️ Important Notes</h3>
        <ul>
          <li>✅ All settings are saved to the server's environment</li>
          <li>🔒 Passwords are stored securely in the .env file</li>
          <li>🔄 Changes take effect immediately</li>
          <li>🧪 Use the test buttons to verify your configuration</li>
          <li>📋 Only admin users can modify these settings</li>
        </ul>
      </div>

      <hr style={{margin: '40px 0', border: '1px solid #eee'}} />

      <h2>👥 User Management</h2>
      <p className="admin-only">👤 Admin only - Create standard user accounts</p>

      {userError && <div className="error-message">{userError}</div>}
      {userSuccess && <div className="success-message">{userSuccess}</div>}

      <form onSubmit={handleCreateUser} className="settings-form">
        <fieldset className="settings-section">
          <legend>➕ Add New User</legend>

          <div className="form-group">
            <label htmlFor="new_username">Username</label>
            <input
              id="new_username"
              type="text"
              value={newUser.username}
              onChange={(e) => setNewUser({...newUser, username: e.target.value})}
              placeholder="Username"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="new_email">Email</label>
            <input
              id="new_email"
              type="email"
              value={newUser.email}
              onChange={(e) => setNewUser({...newUser, email: e.target.value})}
              placeholder="user@example.com"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="new_password">Password</label>
            <input
              id="new_password"
              type="password"
              value={newUser.password}
              onChange={(e) => setNewUser({...newUser, password: e.target.value})}
              placeholder="••••••••"
              required
            />
          </div>

          <div className="form-actions">
            <button type="submit" disabled={userLoading} className="btn-primary">
              {userLoading ? '⏳ Creating...' : '➕ Create User'}
            </button>
          </div>
        </fieldset>
      </form>
    </div>
  );
}

export default SettingsModule;
