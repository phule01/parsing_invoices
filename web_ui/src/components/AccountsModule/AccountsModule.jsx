import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import './AccountsModule.css';

const AccountsModule = ({ onSelectAccount }) => {
  const { token, user } = useAuth();
  const [usersList, setUsersList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchUsers = useCallback(async () => {
    if (!user?.is_admin) return;
    try {
      setLoading(true);
      const apiBaseUrl = process.env.REACT_APP_API_URL || (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : '');
      const response = await fetch(`${apiBaseUrl}/api/auth/admin/users`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (!response.ok) throw new Error('Failed to fetch accounts');
      
      const data = await response.json();
      setUsersList(data);
      setError(null);
    } catch (err) {
      setError(err.message);
      console.error("Failed to fetch users:", err);
    } finally {
      setLoading(false);
    }
  }, [token, user]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  if (!user?.is_admin) {
    return <div className="error-message">Access denied. Admin only.</div>;
  }

  return (
    <div className="accounts-module">
      <div className="module-header">
        <h1>👥 Accounts Workspace</h1>
        <button className="btn-refresh" onClick={fetchUsers}>
          🔄 Refresh
        </button>
      </div>

      {error && <div className="error-message">⚠️ {error}</div>}

      <div className="accounts-list-container">
        {loading ? (
          <div className="loading">Loading accounts...</div>
        ) : usersList.length === 0 ? (
          <div className="empty-state">No active user accounts found.</div>
        ) : (
          <div className="accounts-grid">
            {usersList.map((u) => (
              <div key={u.id} className="account-card">
                <div className="account-card-header">
                  <h3>{u.username}</h3>
                  {u.is_admin ? (
                     <span className="badge admin-badge">Admin</span>
                  ) : (
                     <span className="badge user-badge">User</span>
                  )}
                </div>
                <div className="account-card-body">
                  <p><strong>Email:</strong> {u.email || 'N/A'}</p>
                  <p><strong>Created:</strong> {u.created_at ? new Date(u.created_at).toLocaleDateString() : 'N/A'}</p>
                </div>
                <div className="account-card-actions">
                  <button 
                    className="btn-view-workspace"
                    onClick={() => onSelectAccount(u)}
                  >
                    View Workspace ➔
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default AccountsModule;
