import React, { useState, useEffect, useCallback } from 'react';
import './InventoryDashboard.css';
import { useAuth } from '../../context/AuthContext';

/**
 * Inventory Dashboard Component
 * 
 * Features:
 * - View current inventory (product name + total quantity)
 * - Real-time updates after invoice approval
 * - Low stock alerts
 * - Inventory statistics summary
 * - Product audit history view
 */
const InventoryDashboard = ({ 
  apiBaseUrl = process.env.REACT_APP_API_URL || (process.env.NODE_ENV === 'development' ? 'http://localhost:8000/api' : '/api'),
  adminTargetUser
}) => {
  const { token, user } = useAuth();
  const [inventory, setInventory] = useState([]);
  const [summary, setSummary] = useState(null);
  const [lowStockItems, setLowStockItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [auditHistory, setAuditHistory] = useState([]);
  const [refreshInterval, setRefreshInterval] = useState(5000); // Auto-refresh every 5 seconds
  const [showAuditModal, setShowAuditModal] = useState(false);

  // Local user filter removed, now passed as prop `adminTargetUser`

  // Fetch current inventory
  const fetchInventory = useCallback(async () => {
    try {
      setError(null);
      let url = `${apiBaseUrl}/products/?limit=100`;
      if (adminTargetUser?.id) url += `&target_user_id=${adminTargetUser.id}`;
      const response = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!response.ok) throw new Error('Failed to fetch inventory');
      const data = await response.json();
      setInventory(data);
    } catch (err) {
      setError(err.message);
      console.error('Error fetching inventory:', err);
    }
  }, [apiBaseUrl, token, adminTargetUser]);

  // Fetch inventory summary
  const fetchSummary = useCallback(async () => {
    try {
      let url = `${apiBaseUrl}/products/`;
      if (adminTargetUser?.id) url += `?target_user_id=${adminTargetUser.id}`;
      const response = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!response.ok) throw new Error('Failed to fetch summary');
      const data = await response.json();
      // Calculate summary from products
      setSummary({
        total_products: data.length,
        total_value: data.reduce((sum, p) => sum + (p.price * p.quantity_in_stock), 0),
        total_quantity: data.reduce((sum, p) => sum + p.quantity_in_stock, 0)
      });
    } catch (err) {
      console.error('Error fetching summary:', err);
    }
  }, [apiBaseUrl, token, adminTargetUser]);

  // Fetch low stock items
  const fetchLowStockItems = useCallback(async () => {
    try {
      let url = `${apiBaseUrl}/products/`;
      if (adminTargetUser?.id) url += `?target_user_id=${adminTargetUser.id}`;
      const response = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!response.ok) throw new Error('Failed to fetch low stock items');
      const data = await response.json();
      // Filter items with low stock (quantity_in_stock < 10)
      const lowStock = data.filter(p => p.quantity_in_stock < 10);
      setLowStockItems(lowStock);
    } catch (err) {
      console.error('Error fetching low stock items:', err);
    }
  }, [apiBaseUrl, token, adminTargetUser]);

  // Fetch audit history for a product
  const fetchAuditHistory = useCallback(async (productId) => {
    try {
      const response = await fetch(
        `${apiBaseUrl}/products/${productId}/audit-history?limit=20`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!response.ok) throw new Error('Failed to fetch audit history');
      const data = await response.json();
      setAuditHistory(data);
    } catch (err) {
      console.error('Error fetching audit history:', err);
    }
  }, [apiBaseUrl, token]);

  // Initial load and setup auto-refresh
  useEffect(() => {
    fetchInventory();
    fetchSummary();
    fetchLowStockItems();
    setLoading(false);

    // Set up auto-refresh interval
    const interval = setInterval(() => {
      fetchInventory();
      fetchSummary();
      fetchLowStockItems();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [refreshInterval, fetchInventory, fetchSummary, fetchLowStockItems, adminTargetUser]);

  // Handle product selection to view audit history
  const handleViewAuditHistory = (product) => {
    setSelectedProduct(product);
    fetchAuditHistory(product.id);
    setShowAuditModal(true);
  };

  const closeAuditModal = () => {
    setShowAuditModal(false);
    setSelectedProduct(null);
    setAuditHistory([]);
  };

  return (
    <div className="inventory-dashboard">
      {/* Header */}
      <div className="dashboard-header">
        <h1>📦 Inventory Management</h1>
        <div className="header-controls">
          <button 
            className="btn-refresh"
            onClick={() => {
              setLoading(true);
              fetchInventory();
              fetchSummary();
              fetchLowStockItems();
              setLoading(false);
            }}
          >
            🔄 Refresh
          </button>
          <select 
            value={refreshInterval} 
            onChange={(e) => setRefreshInterval(Number(e.target.value))}
            className="refresh-interval"
          >
            <option value={3000}>Auto-refresh: 3s</option>
            <option value={5000}>Auto-refresh: 5s</option>
            <option value={10000}>Auto-refresh: 10s</option>
            <option value={0}>Manual only</option>
          </select>
        </div>
      </div>

      {error && <div className="error-message">⚠️ {error}</div>}

      {/* Summary Cards */}
      {summary && (
        <div className="summary-cards">
          <div className="card total-products">
            <div className="card-value">{summary.total_products}</div>
            <div className="card-label">Total Products</div>
          </div>
          <div className="card total-units">
            <div className="card-value">{summary.total_units_in_stock}</div>
            <div className="card-label">Units in Stock</div>
          </div>
          <div className="card total-value">
            <div className="card-value">
              {new Intl.NumberFormat('vi-VN', {
                style: 'currency',
                currency: 'VND',
                maximumFractionDigits: 0,
              }).format(summary.total_inventory_value)}
            </div>
            <div className="card-label">Total Value</div>
          </div>
          <div className="card last-updated">
            <div className="card-value">
              {summary.last_updated 
                ? new Date(summary.last_updated).toLocaleTimeString()
                : 'N/A'
              }
            </div>
            <div className="card-label">Last Updated</div>
          </div>
        </div>
      )}

      {/* Low Stock Alert */}
      {lowStockItems.length > 0 && (
        <div className="alert-section">
          <h3>⚠️ Low Stock Alert ({lowStockItems.length})</h3>
          <div className="low-stock-list">
            {lowStockItems.map((item) => (
              <div key={item.id} className={`low-stock-item ${item.status}`}>
                <div className="item-name">{item.name}</div>
                <div className="item-quantity">
                  Qty: <strong>{item.quantity_in_stock}</strong>
                </div>
                <div className={`item-status ${item.status}`}>
                  {item.status === 'critical' ? '🔴 CRITICAL' : '🟡 LOW'}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Main Inventory Table */}
      <div className="inventory-section">
        <h2>Current Inventory</h2>
        {loading ? (
          <div className="loading">Loading inventory data...</div>
        ) : inventory.length === 0 ? (
          <div className="empty-state">
            <p>📭 No products in inventory yet.</p>
            <p>Approved invoices will appear here automatically.</p>
          </div>
        ) : (
          <div className="table-container">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Product Name</th>
                  <th className="qty-column">Quantity</th>
                  <th className="price-column">Unit Price</th>
                  <th className="actions-column">Actions</th>
                </tr>
              </thead>
              <tbody>
                {inventory.map((item, index) => (
                  <tr key={item.id} className={item.quantity_in_stock === 0 ? 'out-of-stock' : ''}>
                    <td>{index + 1}</td>
                    <td className="product-name">{item.name}</td>
                    <td className="qty-column">
                      <span className="quantity-badge">
                        {item.quantity_in_stock}
                      </span>
                    </td>
                    <td className="price-column">
                      {new Intl.NumberFormat('vi-VN', {
                        style: 'currency',
                        currency: 'VND',
                        maximumFractionDigits: 0,
                      }).format(item.price)}
                    </td>
                    <td className="actions-column">
                      <button
                        className="btn-audit"
                        onClick={() => handleViewAuditHistory(item)}
                        title="View change history"
                      >
                        📋 History
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Audit History Modal */}
      {showAuditModal && selectedProduct && (
        <div className="modal-overlay">
          <div className="modal">
            <div className="modal-header">
              <h3>📋 Inventory History: {selectedProduct.name}</h3>
              <button className="btn-close" onClick={closeAuditModal}>✕</button>
            </div>
            <div className="modal-body">
              {auditHistory.length === 0 ? (
                <p className="empty">No history available</p>
              ) : (
                <div className="audit-timeline">
                  {auditHistory.map((log) => (
                    <div key={log.id} className={`timeline-item ${log.action}`}>
                      <div className="timeline-date">
                        {new Date(log.created_at).toLocaleString()}
                      </div>
                      <div className="timeline-content">
                        <div className="action-badge">{log.action}</div>
                        <div className="quantity-change">
                          {log.old_quantity} → {log.new_quantity}
                          <span className="change-badge">
                            {log.quantity_change > 0 ? '+' : ''}{log.quantity_change}
                          </span>
                        </div>
                        {log.reason && (
                          <div className="reason">{log.reason}</div>
                        )}
                        {log.invoice_id && (
                          <div className="invoice-ref">
                            Invoice #{log.invoice_id}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn-close-modal" onClick={closeAuditModal}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default InventoryDashboard;
