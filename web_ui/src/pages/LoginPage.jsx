import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import './LoginPage.css';

function LoginPage() {
  const { login, loading, error } = useAuth();
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin');
  const [localError, setLocalError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLocalError('');
    
    try {
      await login(username, password);
    } catch (err) {
      setLocalError(err.message || 'Login failed. Please try again.');
    }
  };

  return (
    <div className="login-page">
      <div className="login-container">
        <div className="login-box">
          <h1>Invoice Management System</h1>
          <p className="subtitle">Dashboard & Telegram Bot Integration</p>

          <form onSubmit={handleSubmit}>
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
              <div className="error-message">
                {error || localError}
              </div>
            )}

            <button type="submit" disabled={loading} className="login-button">
              {loading ? 'Logging in...' : 'Login'}
            </button>
          </form>

          <div className="demo-info">
            <h3>Demo Credentials:</h3>
            <p><strong>Username:</strong> admin</p>
            <p><strong>Password:</strong> admin</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;
