import React, { useState, useEffect, useCallback } from 'react';
import { useWebSocket } from '../../context/WebSocketContext';
import { useInvoiceActions } from '../../hooks/useInvoiceActions';
import {
  fetchInvoices as fetchInvoicesApi,
  fetchInvoice as fetchInvoiceApi,
  createInvoice as createInvoiceApi,
  triggerEmailScan,
} from '../../api/invoiceApi';
import { useAuth } from '../../context/AuthContext';
import InvoiceDetailsModal from './InvoiceDetailsModal';
import './InvoiceModule.css';

const API_BASE = process.env.REACT_APP_API_URL || (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : '');

// ── Constants ─────────────────────────────────────────────────────────────────

const EMPTY_FORM = {
  invoice_number: '',
  invoice_date: new Date().toISOString().split('T')[0],
  buyer_name: '',
  items: [],
  total_amount: 0,
};

const EMPTY_DELETE_MODAL = {
  show: false,
  invoiceId: null,
  invoiceNumber: null,
  productCount: 0,
};

const STATUS_LABELS = {
  pending:  '⏳ Pending',
  verified: '✅ Verified',
  rejected: '❌ Rejected',
  synced:   '📤 Synced',
};

// ── Component ─────────────────────────────────────────────────────────────────

function InvoiceModule({ adminTargetUser }) {
  const { token } = useAuth();
  const { subscribe } = useWebSocket();

  const { approve, reject, remove, isApproving, isRejecting, isDeleting } =
    useInvoiceActions();

  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [checkMailRunning, setCheckMailRunning] = useState(false);
  const [checkMailStatus, setCheckMailStatus] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [deleteModal, setDeleteModal] = useState(EMPTY_DELETE_MODAL);
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  
  // Local user filter removed, now passed as prop `adminTargetUser`

  const loadInvoices = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchInvoicesApi(token, {
        status: statusFilter || undefined,
        search: searchTerm || undefined,
        target_user_id: adminTargetUser?.id || undefined,
        limit: 100,
      });
      setInvoices(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, statusFilter, searchTerm, adminTargetUser]);

  useEffect(() => { loadInvoices(); }, [loadInvoices]);

  useEffect(() => {
    return subscribe('invoice_created', () => loadInvoices());
  }, [subscribe, loadInvoices]);

  const handleViewInvoice = async (invoiceId) => {
    try {
      const fullInvoice = await fetchInvoiceApi(token, invoiceId);
      setSelectedInvoice(fullInvoice);
    } catch (err) {
      setError('Failed to fetch invoice details: ' + err.message);
    }
  };

  // ── Mail scan ───────────────────────────────────────────────────────────────

  const handleCheckMail = async () => {
    if (checkMailRunning) return;
    setCheckMailRunning(true);
    setCheckMailStatus('Checking mail...');
    try {
      const result = await triggerEmailScan(token, 'unseen');
      const summary = result?.result
        ? `Scan complete: ${result.result.emails} emails, ${result.result.processed} processed.`
        : 'Scan complete.';
      setCheckMailStatus(summary);
    } catch (err) {
      setCheckMailStatus(err.status === 409 ? 'Scan already running.' : err.message);
    } finally {
      setCheckMailRunning(false);
    }
  };

  // ── Invoice actions ─────────────────────────────────────────────────────────

  const handleApprove = async (invoiceId) => {
    try {
      await approve(invoiceId, loadInvoices);
    } catch (err) {
      setError(err.message);
      alert(`❌ Error: ${err.message}`);
    }
  };

  const handleReject = async (invoiceId) => {
    try {
      await reject(invoiceId, loadInvoices);
    } catch (err) {
      setError(err.message);
      alert(`❌ Error: ${err.message}`);
    }
  };

  const handleOpenDeleteModal = (invoice) => {
    setDeleteModal({
      show: true,
      invoiceId: invoice.id,
      invoiceNumber: invoice.invoice_number,
      productCount: invoice.items?.length ?? 0,
    });
  };

  const handleDeleteInvoice = async (cascade) => {
    const { invoiceId, invoiceNumber } = deleteModal;
    setDeleteModal(EMPTY_DELETE_MODAL);
    try {
      await remove(invoiceId, { cascade }, () => {
        alert(cascade
          ? `✅ Invoice ${invoiceNumber} deleted and inventory reverted`
          : `✅ Invoice ${invoiceNumber} deleted`
        );
        loadInvoices();
      });
    } catch (err) {
      setError(err.message);
      alert(`❌ ${err.message}`);
    }
  };

  // ── Create invoice ──────────────────────────────────────────────────────────

  const handleCreateInvoice = async (e) => {
    e.preventDefault();
    try {
      await createInvoiceApi(token, {
        ...formData,
        invoice_date: new Date(formData.invoice_date).toISOString(),
        items: [{
          item_name: 'Sample Item',
          unit: 'pcs',
          quantity: 1,
          unit_price: formData.total_amount,
          total_price: formData.total_amount,
          vat_rate: 0,
        }],
      });
      setShowAddForm(false);
      setFormData(EMPTY_FORM);
      loadInvoices();
    } catch (err) {
      setError(err.message);
    }
  };

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="invoice-module">

      <div className="module-header">
        <h2>📄 Invoices</h2>
        <button onClick={() => setShowAddForm(!showAddForm)} className="btn-primary">
          {showAddForm ? 'Cancel' : '+ Add Invoice'}
        </button>
      </div>

      <div className="check-mail-section">
        <button onClick={handleCheckMail} className="btn-check-mail" disabled={checkMailRunning}>
          {checkMailRunning ? '⏳ Checking mail...' : '📥 Check Mail Now'}
        </button>
        {checkMailStatus && <span className="mail-status">{checkMailStatus}</span>}
      </div>

      <div className="filters-section">
        <input
          type="text"
          placeholder="Search invoices..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="filter-input"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="filter-select"
        >
          <option value="">All Status</option>
          <option value="pending">Pending</option>
          <option value="verified">Verified</option>
          <option value="synced">Synced</option>
        </select>
      </div>

      {showAddForm && (
        <form onSubmit={handleCreateInvoice} className="add-form">
          <h3>Add New Invoice</h3>
          <div className="form-group">
            <label>Invoice Number</label>
            <input type="text" required value={formData.invoice_number}
              onChange={(e) => setFormData({ ...formData, invoice_number: e.target.value })}
              placeholder="e.g., INV-001" />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Invoice Date</label>
              <input type="date" required value={formData.invoice_date}
                onChange={(e) => setFormData({ ...formData, invoice_date: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Total Amount</label>
              <input type="number" required min="0" step="0.01" value={formData.total_amount}
                onChange={(e) => setFormData({ ...formData, total_amount: parseFloat(e.target.value) })} />
            </div>
          </div>
          <div className="form-group">
            <label>Buyer Name</label>
            <input type="text" required value={formData.buyer_name}
              onChange={(e) => setFormData({ ...formData, buyer_name: e.target.value })}
              placeholder="Enter buyer name" />
          </div>
          <div className="form-actions">
            <button type="submit" className="btn-primary">Save Invoice</button>
            <button type="button" onClick={() => setShowAddForm(false)} className="btn-secondary">Cancel</button>
          </div>
        </form>
      )}

      {error && <div className="error-message">{error}</div>}
      {loading && <div className="loading">Loading invoices...</div>}

      {!loading && invoices.length === 0 ? (
        <div className="empty-state"><p>No invoices found</p></div>
      ) : (
        <div className="invoices-table-wrapper">
          <table className="invoices-table">
            <thead>
              <tr>
                <th>Lookup Code</th>
                <th>Series</th>
                <th>Invoice #</th>
                <th>Date</th>
                <th>Buyer</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((invoice) => (
                <tr key={invoice.id} className={`status-${invoice.status}`}>
                  <td><code>{invoice.lookup_code || '—'}</code></td>
                  <td>{invoice.invoice_series || '—'}</td>
                  <td><strong>{invoice.invoice_number}</strong></td>
                  <td>{invoice.invoice_date ? new Date(invoice.invoice_date).toLocaleDateString() : '—'}</td>
                  <td>{invoice.buyer_name}</td>
                  <td>{(invoice.total_amount || 0).toLocaleString('vi-VN')} VND</td>
                  <td>
                    <span className={`badge badge-${invoice.status}`}>
                      {STATUS_LABELS[invoice.status] ?? invoice.status}
                    </span>
                  </td>
                  <td>
                    <InvoiceRowActions
                      invoice={invoice}
                      onView={() => handleViewInvoice(invoice.id)}
                      onApprove={handleApprove}
                      onReject={handleReject}
                      onDelete={handleOpenDeleteModal}
                      isApproving={isApproving(invoice.id)}
                      isRejecting={isRejecting(invoice.id)}
                      isDeleting={isDeleting(invoice.id)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {deleteModal.show && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3>🗑️ Delete Invoice</h3>
            <p><strong>Invoice Number:</strong> {deleteModal.invoiceNumber}</p>
            <p><strong>Products in this invoice:</strong> {deleteModal.productCount}</p>
            <p className="warning-text">⚠️ This action cannot be undone!</p>
            <div className="modal-options">
              <div className="option-card">
                <h4>Option 1: Delete Invoice &amp; Revert Inventory</h4>
                <p>Remove this invoice and subtract {deleteModal.productCount} product(s) from stock</p>
                <button onClick={() => handleDeleteInvoice(true)} className="btn-delete-cascade">
                  🗑️ Delete All
                </button>
              </div>
              <div className="option-card">
                <h4>Option 2: Delete Invoice Only</h4>
                <p>Remove only this invoice, keep all {deleteModal.productCount} products in inventory</p>
                <button onClick={() => handleDeleteInvoice(false)} className="btn-delete-only">
                  📋 Delete Invoice
                </button>
              </div>
            </div>
            <div className="modal-actions">
              <button onClick={() => setDeleteModal(EMPTY_DELETE_MODAL)} className="btn-cancel">
                ❌ Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <InvoiceDetailsModal 
        invoice={selectedInvoice} 
        onClose={() => setSelectedInvoice(null)} 
      />
    </div>
  );
}

// ── Row actions sub-component ─────────────────────────────────────────────────

function InvoiceRowActions({ invoice, onView, onApprove, onReject, onDelete, isApproving, isRejecting, isDeleting }) {
  const busy = isApproving || isRejecting || isDeleting;
  return (
    <div className="action-buttons">
      <button onClick={onView} className="btn-secondary" style={{ marginRight: '5px' }}>
        🔍 View
      </button>
      {invoice.status === 'pending' && (
        <>
          <button onClick={() => onApprove(invoice.id)} className="btn-approve" disabled={busy}>
            {isApproving ? '⏳' : '✅'} Approve
          </button>
          <button onClick={() => onReject(invoice.id)} className="btn-reject" disabled={busy}>
            {isRejecting ? '⏳' : '❌'} Reject
          </button>
        </>
      )}
      <button onClick={() => onDelete(invoice)} className="btn-delete" disabled={busy}>
        {isDeleting ? '⏳' : '🗑️'} Delete
      </button>
    </div>
  );
}

export default InvoiceModule;
