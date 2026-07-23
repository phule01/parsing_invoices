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
  const [emailStep, setEmailStep] = useState(1);
  const [teleStep, setTeleStep] = useState(1);
  const [zoomImage, setZoomImage] = useState(null);

  // Mandatory Test Verification State
  const [emailTested, setEmailTested] = useState(false);
  const [telegramTested, setTelegramTested] = useState(false);

  // Admin Pending Users State
  const [pendingUsers, setPendingUsers] = useState([]);
  const [approvalLoading, setApprovalLoading] = useState(false);

  const [settings, setSettings] = useState({
    EMAIL_ADDRESS: '',
    EMAIL_PASSWORD: '',
    TELEGRAM_BOT_TOKEN: '',
    TELEGRAM_CHAT_ID: '',
    GEMINI_API_KEY: '',
  });

  // ESC key to close lightbox modal
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') setZoomImage(null);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Fetch current settings
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/settings/`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!response.ok) throw new Error('Failed to fetch settings');

        const data = await response.json();
        setSettings(data);

        if (data.EMAIL_ADDRESS && data.HAS_EMAIL_PASSWORD) {
          setEmailTested(true);
        }
        if (data.TELEGRAM_BOT_TOKEN && data.TELEGRAM_CHAT_ID) {
          setTelegramTested(true);
        }
      } catch (err) {
        setError(err.message);
      }
    };

    const fetchPendingUsers = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/auth/admin/pending-users`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (response.ok) {
          const data = await response.json();
          setPendingUsers(data);
        }
      } catch (err) {
        console.error('Failed to fetch pending users:', err);
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

    const hasEmailPassword = settings.EMAIL_PASSWORD || settings.HAS_EMAIL_PASSWORD;
    if (!settings.EMAIL_ADDRESS || !hasEmailPassword || !settings.TELEGRAM_BOT_TOKEN || !settings.TELEGRAM_CHAT_ID) {
      setError('⚠️ Fill in every required field and run a successful connection test before saving.');
      return;
    }

    if (!emailTested) {
      setError('⚠️ You must successfully test your Email connection before saving settings.');
      return;
    }
    if (!telegramTested) {
      setError('⚠️ You must successfully test your Telegram connection before saving settings.');
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/settings/update`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to update settings');
      }

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
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          target_email: settings.EMAIL_ADDRESS,
          email_address: settings.EMAIL_ADDRESS,
          email_password: settings.EMAIL_PASSWORD || '',
        }),
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
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          bot_token: settings.TELEGRAM_BOT_TOKEN,
          chat_id: settings.TELEGRAM_CHAT_ID,
        }),
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

  const handleApproveUser = async (userId) => {
    setApprovalLoading(true);
    setError('');
    setSuccess('');
    try {
      const response = await fetch(`${API_BASE}/api/auth/admin/approve-user/${userId}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Failed to approve user');
      setSuccess('User approved successfully!');
      setPendingUsers(pendingUsers.filter((u) => u.id !== userId));
      setTimeout(() => setSuccess(''), 5000);
    } catch (err) {
      setError(err.message);
    } finally {
      setApprovalLoading(false);
    }
  };

  const handleRejectUser = async (userId) => {
    if (!window.confirm('Are you sure you want to reject this user? Their request will be deleted.')) return;
    setApprovalLoading(true);
    setError('');
    setSuccess('');
    try {
      const response = await fetch(`${API_BASE}/api/auth/admin/reject-user/${userId}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error('Failed to reject user');
      setSuccess('User rejected and removed.');
      setPendingUsers(pendingUsers.filter((u) => u.id !== userId));
      setTimeout(() => setSuccess(''), 5000);
    } catch (err) {
      setError(err.message);
    } finally {
      setApprovalLoading(false);
    }
  };

  return (
    <div id="page-settings" className="page active">
      <div className="page-header">
        <h2>
          <span className="eyebrow">Configuration</span>Settings &amp; Integrations
        </h2>
      </div>

      {error && (
        <div className="warn-banner alert-error-banner" style={{ background: 'rgba(179,49,44,0.08)', borderColor: 'var(--seal)', color: 'var(--seal-dark)', marginBottom: '20px' }}>
          {error}
        </div>
      )}
      {success && (
        <div className="info-note alert-success-note" style={{ background: 'var(--approve-soft)', color: 'var(--approve)', borderLeftColor: 'var(--approve)', marginTop: 0, marginBottom: '20px' }}>
          {success}
        </div>
      )}

      <div className="settings-layout">
        {/* Left Column: Config Forms */}
        <div className="settings-main-col">
          <div className="guide">
            <h4>📋 Quick Setup Summary</h4>
            <ol>
              <li>
                <b>Email Password</b> — generate a 16‑character{' '}
                <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noopener noreferrer">
                  Google App Password
                </a>
                . (Requires 2-Step Verification ON).
              </li>
              <li>
                <b>Telegram Bot Token</b> — message{' '}
                <a href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer">
                  @BotFather
                </a>{' '}
                on Telegram (/newbot), copy the HTTP API token.
              </li>
              <li>
                <b>Telegram Chat ID</b> — message your new bot, then forward to{' '}
                <a href="https://t.me/userinfobot" target="_blank" rel="noopener noreferrer">
                  @userinfobot
                </a>{' '}
                to get your chat ID.
              </li>
            </ol>
          </div>

          <form onSubmit={handleSubmit} className="settings-form">
            {/* Gmail Config */}
            <div className="panel card-block">
              <div className="card-block-head">
                <h3>✉ Email Configuration (Gmail)</h3>
                <span className={`verified-pill ${emailTested ? '' : 'unverified'}`}>
                  {emailTested ? '✓ Verified' : '⚠ Test Required'}
                </span>
              </div>
              <div className="field">
                <label>Email Address</label>
                <input
                  type="email"
                  name="EMAIL_ADDRESS"
                  value={settings.EMAIL_ADDRESS || ''}
                  onChange={handleChange}
                  placeholder="phulehoccode@gmail.com"
                  required
                />
                <div className="help-text">Your personal Gmail account to monitor for invoices.</div>
              </div>
              <div className="field">
                <label>Email App Password</label>
                <input
                  type="password"
                  name="EMAIL_PASSWORD"
                  value={settings.EMAIL_PASSWORD || ''}
                  onChange={handleChange}
                  placeholder={settings.HAS_EMAIL_PASSWORD ? '••••••••••••••••' : '16-character Google App Password'}
                />
                <div className="help-text" style={{ color: 'var(--seal)' }}>
                  Do not enter your normal Gmail password — Google requires a 16‑character App Password.
                </div>
              </div>
              <button
                type="button"
                className="btn-test"
                onClick={handleTestEmail}
                disabled={!!testInProgress}
              >
                {testInProgress === 'email' ? 'Testing Email...' : 'Test Email Connection'}
              </button>
            </div>

            {/* Telegram Config */}
            <div className="panel card-block">
              <div className="card-block-head">
                <h3>📨 Telegram Configuration</h3>
                <span className={`verified-pill ${telegramTested ? '' : 'unverified'}`}>
                  {telegramTested ? '✓ Verified' : '⚠ Test Required'}
                </span>
              </div>
              <div className="field">
                <label>Telegram Bot Token</label>
                <input
                  type="password"
                  name="TELEGRAM_BOT_TOKEN"
                  value={settings.TELEGRAM_BOT_TOKEN || ''}
                  onChange={handleChange}
                  placeholder="123456:ABC-DEF..."
                  required
                />
              </div>
              <div className="field">
                <label>Telegram Chat ID</label>
                <input
                  type="text"
                  name="TELEGRAM_CHAT_ID"
                  value={settings.TELEGRAM_CHAT_ID || ''}
                  onChange={handleChange}
                  placeholder="8269871698"
                  required
                />
                <div className="help-text">Your personal chat ID to receive approval requests from your bot.</div>
              </div>
              <button
                type="button"
                className="btn-test"
                onClick={handleTestTelegram}
                disabled={!!testInProgress}
              >
                {testInProgress === 'telegram' ? 'Testing Telegram...' : 'Test Telegram Message'}
              </button>
            </div>

            {/* Collapsible Gemini AI Config (Hidden by default like old logic) */}
            <details className="panel card-block collapsible-ai-panel">
              <summary className="ai-summary-header">
                🤖 AI Parser Configuration (Advanced)
              </summary>
              <div className="ai-content-body" style={{ marginTop: '16px' }}>
                <div className="field">
                  <label>Gemini API Key</label>
                  <input
                    type="password"
                    name="GEMINI_API_KEY"
                    value={settings.GEMINI_API_KEY || ''}
                    onChange={handleChange}
                    placeholder="Leave blank to use default system key"
                  />
                  <div className="help-text">
                    Your personal Gemini API key for invoice parsing. Leave blank to use system default.
                  </div>
                </div>
              </div>
            </details>

            <button type="submit" className="btn-save" disabled={loading}>
              {loading ? 'Saving...' : 'Save Settings'}
            </button>
          </form>

          {/* Pending Approvals Section for Admin */}
          {user?.is_admin && pendingUsers.length > 0 && (
            <div className="panel card-block" style={{ marginTop: '22px' }}>
              <div className="card-block-head">
                <h3>👥 Pending User Approvals ({pendingUsers.length})</h3>
              </div>
              <div className="pending-users-list">
                {pendingUsers.map((pUser) => (
                  <div key={pUser.id} className="pending-user-item">
                    <div>
                      <b>{pUser.username}</b>
                    </div>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button
                        className="act approve"
                        onClick={() => handleApproveUser(pUser.id)}
                        disabled={approvalLoading}
                      >
                        ✓ Approve
                      </button>
                      <button
                        className="act reject"
                        onClick={() => handleRejectUser(pUser.id)}
                        disabled={approvalLoading}
                      >
                        ✕ Reject
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="info-note">ⓘ Integration settings (Email, API, Telegram) are personal to your account.</div>
        </div>

        {/* Right Column: Real Visual Setup Guides */}
        <div className="settings-guide-col">
          {/* Google App Password Guide */}
          <div className="panel card-block visual-guide-card">
            <div className="card-block-head">
              <h3>📖 Google App Password Creation Guide</h3>
            </div>

            <div className="step-tabs">
              <button
                type="button"
                className={`step-tab ${emailStep === 1 ? 'active' : ''}`}
                onClick={() => setEmailStep(1)}
              >
                1. Enable 2FA
              </button>
              <button
                type="button"
                className={`step-tab ${emailStep === 2 ? 'active' : ''}`}
                onClick={() => setEmailStep(2)}
              >
                2. App Passwords
              </button>
              <button
                type="button"
                className={`step-tab ${emailStep === 3 ? 'active' : ''}`}
                onClick={() => setEmailStep(3)}
              >
                3. Name &amp; Create
              </button>
              <button
                type="button"
                className={`step-tab ${emailStep === 4 ? 'active' : ''}`}
                onClick={() => setEmailStep(4)}
              >
                4. Copy Code
              </button>
            </div>

            <div className="step-image-container">
              {emailStep === 1 && (
                <div>
                  <div
                    className="guide-illustration-wrapper"
                    onClick={() =>
                      setZoomImage({
                        src: '/assets/app_password_step1.png',
                        title: 'Google App Password — Step 1: Enable 2-Step Verification',
                      })
                    }
                  >
                    <img
                      src="/assets/app_password_step1.png"
                      alt="Step 1: Check 2-Step Verification"
                      className="guide-illustration"
                    />
                  </div>
                  <p className="help-text">
                    🔒 <b>Step 1: Enable 2-Step Verification</b><br />
                    Open Google Account Security (<code>myaccount.google.com/security</code>). Ensure <b>2-Step Verification</b> is turned <b>ON</b>.
                  </p>
                </div>
              )}
              {emailStep === 2 && (
                <div>
                  <div
                    className="guide-illustration-wrapper"
                    onClick={() =>
                      setZoomImage({
                        src: '/assets/app_password_step2.png',
                        title: 'Google App Password — Step 2: Access App Passwords',
                      })
                    }
                  >
                    <img
                      src="/assets/app_password_step2.png"
                      alt="Step 2: Password Verification"
                      className="guide-illustration"
                    />
                  </div>
                  <p className="help-text">
                    🔑 <b>Step 2: Access App Passwords</b><br />
                    Select <b>App passwords</b> (or visit <code>myaccount.google.com/apppasswords</code>). Re-enter your password to confirm identity.
                  </p>
                </div>
              )}
              {emailStep === 3 && (
                <div>
                  <div
                    className="guide-illustration-wrapper"
                    onClick={() =>
                      setZoomImage({
                        src: '/assets/app_password_step3.png',
                        title: 'Google App Password — Step 3: Name App and Click Create',
                      })
                    }
                  >
                    <img
                      src="/assets/app_password_step3.png"
                      alt="Step 3: Enter App Name and click Create"
                      className="guide-illustration"
                    />
                  </div>
                  <p className="help-text">
                    ✍️ <b>Step 3: Name Your App &amp; Generate</b><br />
                    Type an app name into <i>Tên ứng dụng</i> (e.g. <code>Invoice System</code>) and click <b>Tạo / Create</b>.
                  </p>
                </div>
              )}
              {emailStep === 4 && (
                <div>
                  <div
                    className="guide-illustration-wrapper"
                    onClick={() =>
                      setZoomImage({
                        src: '/assets/app_password_step4.png',
                        title: 'Google App Password — Step 4: Copy Generated 16-Character Code',
                      })
                    }
                  >
                    <img
                      src="/assets/app_password_step4.png"
                      alt="Step 4: Copy 16-character generated code"
                      className="guide-illustration"
                    />
                  </div>
                  <p className="help-text">
                    📋 <b>Step 4: Copy 16-Character Code</b><br />
                    Copy the generated 16-character password (e.g. <code>abcd efgh ijkl mnop</code>) and paste it into the <b>Email App Password</b> field on the left.
                  </p>
                </div>
              )}
            </div>

            <div className="guide-nav-buttons">
              <button
                type="button"
                className="btn-ghost"
                disabled={emailStep === 1}
                onClick={() => setEmailStep((prev) => Math.max(1, prev - 1))}
              >
                ← Previous
              </button>
              <span className="code">Step {emailStep} of 4</span>
              <button
                type="button"
                className="btn-ghost"
                disabled={emailStep === 4}
                onClick={() => setEmailStep((prev) => Math.min(4, prev + 1))}
              >
                Next →
              </button>
            </div>

            <div className="guide-actions" style={{ marginTop: '14px' }}>
              <a
                href="https://myaccount.google.com/apppasswords"
                target="_blank"
                rel="noopener noreferrer"
                className="btn-ghost guide-btn"
              >
                ↗ Open Google App Passwords
              </a>
              <a
                href="https://myaccount.google.com/signinoptions/two-step-verification"
                target="_blank"
                rel="noopener noreferrer"
                className="btn-ghost guide-btn"
              >
                🔒 Enable 2-Step Verification
              </a>
            </div>
          </div>

          {/* Telegram Bot Setup Guide */}
          <div className="panel card-block visual-guide-card">
            <div className="card-block-head">
              <h3>📱 Telegram Bot Setup Guide</h3>
            </div>

            <div className="step-tabs">
              <button
                type="button"
                className={`step-tab ${teleStep === 1 ? 'active' : ''}`}
                onClick={() => setTeleStep(1)}
              >
                1. Find @BotFather
              </button>
              <button
                type="button"
                className={`step-tab ${teleStep === 2 ? 'active' : ''}`}
                onClick={() => setTeleStep(2)}
              >
                2. Get Token
              </button>
              <button
                type="button"
                className={`step-tab ${teleStep === 3 ? 'active' : ''}`}
                onClick={() => setTeleStep(3)}
              >
                3. Start Bot
              </button>
              <button
                type="button"
                className={`step-tab ${teleStep === 4 ? 'active' : ''}`}
                onClick={() => setTeleStep(4)}
              >
                4. Find @userinfobot
              </button>
              <button
                type="button"
                className={`step-tab ${teleStep === 5 ? 'active' : ''}`}
                onClick={() => setTeleStep(5)}
              >
                5. Get Chat ID
              </button>
            </div>

            <div className="step-image-container">
              {teleStep === 1 && (
                <div>
                  <div
                    className="guide-illustration-wrapper"
                    onClick={() =>
                      setZoomImage({
                        src: '/assets/telegram_step1.png',
                        title: 'Telegram Setup — Step 1: Search @BotFather',
                      })
                    }
                  >
                    <img
                      src="/assets/telegram_step1.png"
                      alt="Step 1: Search @BotFather on Telegram"
                      className="guide-illustration"
                    />
                  </div>
                  <p className="help-text">
                    🔎 <b>Step 1: Search &amp; Open @BotFather</b><br />
                    Search <b>@BotFather</b> in the Telegram search bar and tap the official account with the blue checkmark.
                  </p>
                </div>
              )}
              {teleStep === 2 && (
                <div>
                  <div
                    className="guide-illustration-wrapper"
                    onClick={() =>
                      setZoomImage({
                        src: '/assets/telegram_step5.png',
                        title: 'Telegram Setup — Step 2: Create Bot & Copy Token',
                      })
                    }
                  >
                    <img
                      src="/assets/telegram_step5.png"
                      alt="Step 2: Create bot with /newbot and copy HTTP API token"
                      className="guide-illustration"
                    />
                  </div>
                  <p className="help-text">
                    🤖 <b>Step 2: Create Bot &amp; Copy HTTP API Token</b><br />
                    Type <code>/newbot</code> in chat. Set a bot Name and Username ending in <code>bot</code> (e.g. <code>zu4b1t_bot</code>). Copy the <b>HTTP API Token</b> (circled in red) into <i>Telegram Bot Token</i> on the left.
                  </p>
                </div>
              )}
              {teleStep === 3 && (
                <div>
                  <div
                    className="guide-illustration-wrapper"
                    onClick={() =>
                      setZoomImage({
                        src: '/assets/telegram_step3.png',
                        title: 'Telegram Setup — Step 3: Start Your Bot ("Bắt đầu Bot")',
                      })
                    }
                  >
                    <img
                      src="/assets/telegram_step3.png"
                      alt="Step 3: Open your bot link and click Bắt đầu Bot / Start"
                      className="guide-illustration"
                    />
                  </div>
                  <p className="help-text">
                    🚀 <b>Step 3: Start Your Bot ("Bắt đầu Bot")</b><br />
                    Click your bot link (e.g. <code>t.me/zu4b1t_bot</code>) from BotFather's message, then press <b>Bắt đầu Bot / Start</b> at the bottom. <i>(Required for receiving notifications!)</i>
                  </p>
                </div>
              )}
              {teleStep === 4 && (
                <div>
                  <div
                    className="guide-illustration-wrapper"
                    onClick={() =>
                      setZoomImage({
                        src: '/assets/telegram_step4.png',
                        title: 'Telegram Setup — Step 4: Search @userinfobot',
                      })
                    }
                  >
                    <img
                      src="/assets/telegram_step4.png"
                      alt="Step 4: Search @userinfobot"
                      className="guide-illustration"
                    />
                  </div>
                  <p className="help-text">
                    🆔 <b>Step 4: Search @userinfobot</b><br />
                    Search <b>@userinfobot</b> in the Telegram search bar to get your personal numerical Chat ID.
                  </p>
                </div>
              )}
              {teleStep === 5 && (
                <div>
                  <div
                    className="guide-illustration-wrapper"
                    onClick={() =>
                      setZoomImage({
                        src: '/assets/telegram_step2.png',
                        title: 'Telegram Setup — Step 5: Copy Numerical Chat ID',
                      })
                    }
                  >
                    <img
                      src="/assets/telegram_step2.png"
                      alt="Step 5: Copy your numerical Chat ID"
                      className="guide-illustration"
                    />
                  </div>
                  <p className="help-text">
                    📋 <b>Step 5: Copy Your Numerical Chat ID</b><br />
                    Send <code>/start</code> or a message to @userinfobot. Copy the numerical number listed next to <b>Id:</b> (e.g. <code>8269871698</code>) into <i>Telegram Chat ID</i> on the left.
                  </p>
                </div>
              )}
            </div>

            <div className="guide-nav-buttons">
              <button
                type="button"
                className="btn-ghost"
                disabled={teleStep === 1}
                onClick={() => setTeleStep((prev) => Math.max(1, prev - 1))}
              >
                ← Previous
              </button>
              <span className="code">Step {teleStep} of 5</span>
              <button
                type="button"
                className="btn-ghost"
                disabled={teleStep === 5}
                onClick={() => setTeleStep((prev) => Math.min(5, prev + 1))}
              >
                Next →
              </button>
            </div>

            <div className="guide-actions" style={{ marginTop: '14px' }}>
              <a
                href="https://t.me/BotFather"
                target="_blank"
                rel="noopener noreferrer"
                className="btn-ghost guide-btn"
              >
                ↗ Open @BotFather
              </a>
              <a
                href="https://t.me/userinfobot"
                target="_blank"
                rel="noopener noreferrer"
                className="btn-ghost guide-btn"
              >
                ↗ Open @userinfobot
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* Full-Screen Image Lightbox Preview Modal */}
      {zoomImage && (
        <div className="image-lightbox-backdrop" onClick={() => setZoomImage(null)}>
          <div className="image-lightbox-card" onClick={(e) => e.stopPropagation()}>
            <div className="lightbox-head">
              <h4>🔍 {zoomImage.title}</h4>
              <button className="lightbox-close-btn" onClick={() => setZoomImage(null)}>
                ✕ Close (ESC)
              </button>
            </div>
            <div className="lightbox-img-wrapper">
              <img src={zoomImage.src} alt={zoomImage.title} className="lightbox-img" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default SettingsModule;
