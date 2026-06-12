import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import './SettingsModule.css';

function SettingsModule() {
  const { token, user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [testInProgress, setTestInProgress] = useState('');

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
        const response = await fetch('http://localhost:8000/api/settings/', {
          headers: { Authorization: `Bearer ${token}` }
        });

        if (response.status === 403) {
          setError('Only admin users can access settings');
          return;
        }

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
      const response = await fetch('http://localhost:8000/api/settings/update', {
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
      const response = await fetch('http://localhost:8000/api/settings/test-email?email_address=' + encodeURIComponent(settings.EMAIL_ADDRESS), {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) throw new Error('Failed to send test email');

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
      const response = await fetch('http://localhost:8000/api/settings/test-telegram', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) throw new Error('Failed to send test message');

      const data = await response.json();
      setSuccess(`✅ ${data.message}`);
      setTimeout(() => setSuccess(''), 5000);
    } catch (err) {
      setError(`❌ Error: ${err.message}`);
    } finally {
      setTestInProgress('');
    }
  };

  return (
    <div className="settings-module">
      <h2>⚙️ System Settings</h2>
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
    </div>
  );
}

export default SettingsModule;
