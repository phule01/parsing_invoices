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

  // Mandatory Test Verification State
  const [emailTested, setEmailTested] = useState(false);
  const [telegramTested, setTelegramTested] = useState(false);
  const [showAppPasswordHelp, setShowAppPasswordHelp] = useState(true);

  // User Management State
  const [newUser, setNewUser] = useState({ username: '', password: '' });
  const [userLoading, setUserLoading] = useState(false);
  const [userSuccess, setUserSuccess] = useState('');
  const [userError, setUserError] = useState('');

  // Pending Approvals State
  const [pendingUsers, setPendingUsers] = useState([]);
  const [approvalLoading, setApprovalLoading] = useState(false);

  const [useCustomGemini, setUseCustomGemini] = useState(false);
  const [settings, setSettings] = useState({
    EMAIL_ADDRESS: '',
    EMAIL_PASSWORD: '',
    GEMINI_API_KEY: '',
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

        // If settings already exist in database, initialize them as verified
        if (data.EMAIL_ADDRESS && data.HAS_EMAIL_PASSWORD) {
          setEmailTested(true);
        }
        if (data.TELEGRAM_BOT_TOKEN && data.TELEGRAM_CHAT_ID) {
          setTelegramTested(true);
        }

        if (data.GEMINI_API_KEY) {
          setUseCustomGemini(true);
        }
      } catch (err) {
        setError(err.message);
      }
    };

    const fetchPendingUsers = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/auth/admin/pending-users`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (response.ok) {
          const data = await response.json();
          setPendingUsers(data);
        }
      } catch (err) {
        console.error("Failed to fetch pending users:", err);
      }
    };

    if (token) {
      fetchSettings();
      if (user?.is_admin) {
        fetchPendingUsers();
      }
    }
  }, [token, user]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setSettings({ ...settings, [name]: value });
    setError('');
    setSuccess('');

    // Invalidate test status when corresponding credentials are modified
    if (name === 'EMAIL_ADDRESS' || name === 'EMAIL_PASSWORD') {
      setEmailTested(false);
    }
    if (name === 'TELEGRAM_BOT_TOKEN' || name === 'TELEGRAM_CHAT_ID') {
      setTelegramTested(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    // 1. Mandatory field validation
    const hasEmailPassword = settings.EMAIL_PASSWORD || settings.HAS_EMAIL_PASSWORD;
    if (!settings.EMAIL_ADDRESS || !hasEmailPassword || !settings.TELEGRAM_BOT_TOKEN || !settings.TELEGRAM_CHAT_ID) {
      setError('⚠️ Please fill in all required configuration fields (Email Address, Email App Password, Telegram Bot Token, Telegram Chat ID).');
      return;
    }

    // 2. Mandatory test verification check
    if (!emailTested) {
      setError('⚠️ You must successfully test your Email Connection before saving settings!');
      return;
    }
    if (!telegramTested) {
      setError('⚠️ You must successfully test your Telegram Message connection before saving settings!');
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/settings/update`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to update settings');
      }

      const data = await response.json();
      setSuccess('✅ Settings verified and saved successfully!');
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
          email_password: settings.EMAIL_PASSWORD || ''
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to send test email');
      }

      const data = await response.json();
      setEmailTested(true);
      setSuccess(`✅ ${data.message}`);
      setTimeout(() => setSuccess(''), 5000);
    } catch (err) {
      setEmailTested(false);
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
      setTelegramTested(true);
      setSuccess(`✅ ${data.message}`);
      setTimeout(() => setSuccess(''), 5000);
    } catch (err) {
      setTelegramTested(false);
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

  const handleApproveUser = async (userId) => {
    setApprovalLoading(true);
    setUserError('');
    setUserSuccess('');
    try {
      const response = await fetch(`${API_BASE}/api/auth/admin/approve-user/${userId}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!response.ok) throw new Error('Failed to approve user');
      setUserSuccess('User approved successfully!');
      setPendingUsers(pendingUsers.filter(u => u.id !== userId));
      setTimeout(() => setUserSuccess(''), 5000);
    } catch (err) {
      setUserError(err.message);
    } finally {
      setApprovalLoading(false);
    }
  };

  const handleRejectUser = async (userId) => {
    if (!window.confirm("Are you sure you want to reject this user? Their request will be deleted.")) return;
    setApprovalLoading(true);
    setUserError('');
    setUserSuccess('');
    try {
      const response = await fetch(`${API_BASE}/api/auth/admin/reject-user/${userId}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!response.ok) throw new Error('Failed to reject user');
      setUserSuccess('User rejected and removed.');
      setPendingUsers(pendingUsers.filter(u => u.id !== userId));
      setTimeout(() => setUserSuccess(''), 5000);
    } catch (err) {
      setUserError(err.message);
    } finally {
      setApprovalLoading(false);
    }
  };

  {/* Admin Section is now just for User Management, handled below */ }



  return (
    <div className="settings-module">
      <h2>⚙️ Settings & Integrations</h2>
      <p>Configure your personal and system integrations here.</p>

      {error && <div className="error-message">{error}</div>}
      {success && <div className="success-message">{success}</div>}


      <div className="settings-guide" style={{ background: '#f8f9fa', padding: '20px', borderRadius: '10px', marginBottom: '20px', borderLeft: '5px solid #007bff', boxShadow: '0 2px 5px rgba(0,0,0,0.05)' }}>
        <h3 style={{ margin: '0 0 15px 0', color: '#333' }}>📖 Quick Setup Guide</h3>
        <ol style={{ margin: 0, paddingLeft: '25px', lineHeight: '1.7', color: '#555' }}>
          <li><strong>Email Password:</strong> Generate a 16-character <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noopener noreferrer">Google App Password</a>. Do not use your regular Gmail password.</li>
          <li><strong>Telegram Bot Token:</strong> Message <a href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer">@BotFather</a> on Telegram, create a new bot (<code>/newbot</code>), and copy the HTTP API Token.</li>
          <li><strong>Telegram Chat ID:</strong> Message your new bot (to start a chat), then forward a message to <a href="https://t.me/userinfobot" target="_blank" rel="noopener noreferrer">@userinfobot</a> to get your numerical Chat ID.</li>
        </ol>
      </div>

      <div className="test-warning-banner">
        <span>⚠️ <strong>Mandatory Verification:</strong> Please fill in all required details and perform successful connection tests for both <strong>Email</strong> and <strong>Telegram</strong> before saving your settings.</span>
      </div>

      <form onSubmit={handleSubmit} className="settings-form">

        {/* Email Configuration */}
        <fieldset className="settings-section">
          <legend>
            📧 Email Configuration (Gmail)
            <span className={`badge-status ${emailTested ? 'badge-success' : 'badge-warning'}`}>
              {emailTested ? '✅ Tested & Verified' : '⚠️ Test Required'}
            </span>
          </legend>
          <div className="form-group">
            <label htmlFor="EMAIL_ADDRESS">Email Address *</label>
            <input
              id="EMAIL_ADDRESS"
              type="email"
              name="EMAIL_ADDRESS"
              value={settings.EMAIL_ADDRESS || ''}
              onChange={handleChange}
              placeholder="your-email@gmail.com"
              required
            />
            <small>Your personal Gmail account to monitor for invoices</small>
          </div>
          <div className="form-group">
            <label htmlFor="EMAIL_PASSWORD" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Email App Password *</span>
              <button 
                type="button" 
                onClick={() => setShowAppPasswordHelp(!showAppPasswordHelp)}
                style={{ background: 'none', border: 'none', color: '#0d6efd', cursor: 'pointer', fontSize: '0.85rem', textDecoration: 'underline' }}
              >
                {showAppPasswordHelp ? '❓ Hide Instructions' : '❓ How to get an App Password?'}
              </button>
            </label>
            <input
              id="EMAIL_PASSWORD"
              type="password"
              name="EMAIL_PASSWORD"
              value={settings.EMAIL_PASSWORD || ''}
              onChange={handleChange}
              placeholder={settings.HAS_EMAIL_PASSWORD ? "•••••••• (Not your normal Gmail password)" : "16-character Google App Password (e.g. abcd efgh ijkl mnop)"}
            />
            <small style={{ color: '#d9534f', display: 'block', marginTop: '4px' }}>
              ⚠️ <strong>Do NOT enter your normal Gmail password!</strong> Google requires a 16-character <em>App Password</em> to securely access your inbox.
            </small>

            {showAppPasswordHelp && (
              <div style={{ marginTop: '12px', padding: '14px 16px', background: '#eef6ff', border: '1px solid #b6d4fe', borderRadius: '8px', fontSize: '0.88rem', color: '#1d3557', lineHeight: '1.6' }}>
                <h4 style={{ margin: '0 0 8px 0', color: '#0d6efd', fontSize: '0.95rem' }}>📖 What is an Email App Password & How to Get It:</h4>
                <p style={{ margin: '0 0 10px 0' }}>
                  An <strong>App Password</strong> is a 16-digit security passcode created by Google so that automated tools (like this invoice system) can read your invoice emails safely without asking for your main Google password.
                </p>
                <ol style={{ margin: 0, paddingLeft: '20px' }}>
                  <li>Make sure <strong>2-Step Verification</strong> is enabled on your Google Account (<a href="https://myaccount.google.com/security" target="_blank" rel="noopener noreferrer">Check Google Security</a>).</li>
                  <li>Click this direct Google link: <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noopener noreferrer" style={{ fontWeight: 'bold' }}>myaccount.google.com/apppasswords</a></li>
                  <li>Enter an App Name (e.g. <code>Invoice System</code>) and click <strong>Create</strong>.</li>
                  <li>Copy the <strong>16-character code</strong> generated by Google (e.g. <code>abcd efgh ijkl mnop</code>) and paste it into the field above!</li>
                </ol>
              </div>
            )}
          </div>
          <div className="form-actions" style={{ marginTop: '10px' }}>
            <button type="button" onClick={handleTestEmail} disabled={!!testInProgress} className="btn-secondary">
              {testInProgress === 'email' ? '⏳ Testing...' : '🧪 Test Email Connection'}
            </button>
          </div>
        </fieldset>

        {/* Telegram Configuration */}
        <fieldset className="settings-section">
          <legend>
            🤖 Telegram Configuration
            <span className={`badge-status ${telegramTested ? 'badge-success' : 'badge-warning'}`}>
              {telegramTested ? '✅ Tested & Verified' : '⚠️ Test Required'}
            </span>
          </legend>
          <div className="form-group">
            <label htmlFor="TELEGRAM_BOT_TOKEN">Telegram Bot Token *</label>
            <input
              id="TELEGRAM_BOT_TOKEN"
              type="password"
              name="TELEGRAM_BOT_TOKEN"
              value={settings.TELEGRAM_BOT_TOKEN || ''}
              onChange={handleChange}
              placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
              required
            />
            <small>Your personal Telegram Bot token</small>
          </div>

          <div className="form-group">
            <label htmlFor="TELEGRAM_CHAT_ID">Telegram Chat ID *</label>
            <input
              id="TELEGRAM_CHAT_ID"
              type="text"
              name="TELEGRAM_CHAT_ID"
              value={settings.TELEGRAM_CHAT_ID || ''}
              onChange={handleChange}
              placeholder="123456789"
              required
            />
            <small>Your personal Chat ID to receive approval requests from your bot.</small>
          </div>

          <div className="form-actions" style={{ marginTop: '10px' }}>
            <button type="button" onClick={handleTestTelegram} disabled={!!testInProgress} className="btn-secondary">
              {testInProgress === 'telegram' ? '⏳ Testing...' : '🧪 Test Telegram Message'}
            </button>
          </div>
        </fieldset>

        {/* AI Configuration */}
        <details className="settings-section" style={{ padding: '15px', border: '1px solid #ddd', borderRadius: '8px', marginBottom: '20px' }}>
          <summary style={{ cursor: 'pointer', fontWeight: 'bold', fontSize: '1.1em', userSelect: 'none' }}>
            🤖 AI Parser Configuration (Advanced)
          </summary>
          <div style={{ marginTop: '20px' }}>
            <div className="form-group" style={{ marginTop: '5px' }}>
              <label htmlFor="GEMINI_API_KEY">Gemini API Key</label>
              <input
                id="GEMINI_API_KEY"
                type="password"
                name="GEMINI_API_KEY"
                value={settings.GEMINI_API_KEY || ''}
                onChange={handleChange}
                placeholder="••••••••••••••••••••••••••••"
              />
              <small>
                Your personal Gemini API key for invoice parsing. Leave blank to use the system default.
              </small>
            </div>
          </div>
        </details>

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
          <li>✅ Integration settings (Email, API, Telegram) are personal to your account.</li>
        </ul>
      </div>

    </div>
  );
}

export default SettingsModule;
