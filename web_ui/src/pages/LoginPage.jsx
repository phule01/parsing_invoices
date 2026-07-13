import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import './LoginPage.css';

const API_BASE = process.env.REACT_APP_API_URL || (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : '');

function LoginPage() {
  const { login, loading, error } = useAuth();
  const [activeTab, setActiveTab] = useState('user'); // 'user' or 'register'
  const [localError, setLocalError] = useState('');

  // User Login Form
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');


  // User Register Form
  const [registerForm, setRegisterForm] = useState({
    username: '',
    password: '',
  });
  const [successMessage, setSuccessMessage] = useState('');



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
      
      setSuccessMessage('Your account has been created. You can now log in.');
      setRegisterForm({ username: '', password: '' });
    } catch (err) {
      setLocalError(err.message || 'Registration failed. Please try again.');
    }
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
              👤 Login
            </button>
            <button
              className={`tab-button ${activeTab === 'register' ? 'active' : ''}`}
              onClick={() => setActiveTab('register')}
            >
              📝 Create Account
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


        </div>
      </div>
    </div>
  );
}

export default LoginPage;
