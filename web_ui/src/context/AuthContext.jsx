import React, { createContext, useState, useContext, useEffect, useCallback } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Check if token exists in localStorage on mount
  useEffect(() => {
    const storedToken = localStorage.getItem('auth_token');
    if (storedToken) {
      validateToken(storedToken);
    } else {
      setLoading(false);
    }
  }, []);

  // Validate token with backend
  const validateToken = async (token) => {
    try {
      const response = await fetch('http://localhost:8000/api/auth/validate-token', {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (response.ok) {
        // Token is valid, fetch user info
        const userResponse = await fetch('http://localhost:8000/api/auth/me', {
          headers: { Authorization: `Bearer ${token}` }
        });
        
        if (userResponse.ok) {
          const userData = await userResponse.json();
          setUser(userData);
          setToken(token);
          setLoading(false);
        } else {
          localStorage.removeItem('auth_token');
          setLoading(false);
        }
      } else {
        localStorage.removeItem('auth_token');
        setLoading(false);
      }
    } catch (err) {
      console.error('Token validation error:', err);
      localStorage.removeItem('auth_token');
      setLoading(false);
    }
  };

  const login = useCallback(async (username, password) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('http://localhost:8000/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Login failed');
      }

      const data = await response.json();
      
      // Store token and user info
      localStorage.setItem('auth_token', data.access_token);
      setToken(data.access_token);
      setUser({
        id: data.user_id,
        username: data.username
      });
      
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('auth_token');
    setUser(null);
    setToken(null);
    setError(null);
  }, []);

  const value = {
    user,
    token,
    loading,
    error,
    login,
    logout,
    isAuthenticated: !!user
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
