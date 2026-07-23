import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import './LoginPage.css';

const API_BASE = process.env.REACT_APP_API_URL || (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : '');

function LoginPage() {
  const { login, loading, error } = useAuth();
  const [activeTab, setActiveTab] = useState('login'); // 'login' or 'create'
  const [localError, setLocalError] = useState('');

  // User Login Form
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  // User Register Form
  const [registerForm, setRegisterForm] = useState({
    username: '',
    password: '',
    confirmPassword: '',
  });
  const [successMessage, setSuccessMessage] = useState('');

  // Handle user login
  const handleUserLogin = async (e) => {
    e.preventDefault();
    setLocalError('');
    setSuccessMessage('');
    try {
      await login(username, password);
    } catch (err) {
      setLocalError(err.message || 'Login failed. Please try again.');
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

    if (registerForm.confirmPassword && registerForm.password !== registerForm.confirmPassword) {
      setLocalError('Passwords do not match');
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/api/auth/register`, {
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

      setSuccessMessage('Account created successfully! You can now log in.');
      setRegisterForm({ username: '', password: '', confirmPassword: '' });
      setActiveTab('login');
    } catch (err) {
      setLocalError(err.message || 'Registration failed. Please try again.');
    }
  };

  return (
    <div id="view-login" className="view active">
      <div className="login-card">
        <div className="brand-mark"><span>HĐ</span></div>
        <h1>Invoice Management System</h1>
        <p className="login-sub">DASHBOARD &amp; TELEGRAM BOT INTEGRATION</p>

        <div className="tab-row">
          <button
            type="button"
            className={`tab-btn ${activeTab === 'login' ? 'active' : ''}`}
            onClick={() => { setActiveTab('login'); setLocalError(''); setSuccessMessage(''); }}
          >
            Login
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'create' ? 'active' : ''}`}
            onClick={() => { setActiveTab('create'); setLocalError(''); setSuccessMessage(''); }}
          >
            Create Account
          </button>
        </div>

        {(error || localError) && (
          <div className="login-alert error">{error || localError}</div>
        )}
        {successMessage && (
          <div className="login-alert success">{successMessage}</div>
        )}

        {/* Login Form */}
        {activeTab === 'login' && (
          <form onSubmit={handleUserLogin} id="login-form">
            <div className="field">
              <label htmlFor="login-username">Username</label>
              <input
                id="login-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your username"
                disabled={loading}
                required
                autoFocus
              />
            </div>
            <div className="field">
              <label htmlFor="login-password">Password</label>
              <input
                id="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                disabled={loading}
                required
              />
            </div>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? 'Logging in...' : 'Log in →'}
            </button>
          </form>
        )}

        {/* Create Account Form */}
        {activeTab === 'create' && (
          <form onSubmit={handleRegister} id="create-form">
            <div className="field">
              <label htmlFor="reg-username">Username</label>
              <input
                id="reg-username"
                type="text"
                value={registerForm.username}
                onChange={(e) => setRegisterForm({ ...registerForm, username: e.target.value })}
                placeholder="Choose a username"
                disabled={loading}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="reg-password">Password</label>
              <input
                id="reg-password"
                type="password"
                value={registerForm.password}
                onChange={(e) => setRegisterForm({ ...registerForm, password: e.target.value })}
                placeholder="Choose a password"
                disabled={loading}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="reg-confirm">Confirm Password</label>
              <input
                id="reg-confirm"
                type="password"
                value={registerForm.confirmPassword}
                onChange={(e) => setRegisterForm({ ...registerForm, confirmPassword: e.target.value })}
                placeholder="Repeat password"
                disabled={loading}
              />
            </div>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? 'Creating account...' : 'Create account →'}
            </button>
          </form>
        )}

        <p className="login-foot">SECURED ACCESS · v2.1</p>
      </div>
    </div>
  );
}

export default LoginPage;
