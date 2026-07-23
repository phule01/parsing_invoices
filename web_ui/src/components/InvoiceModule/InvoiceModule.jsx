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

  useEffect(() => {
    loadInvoices();
  }, [loadInvoices]);

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
        alert(
          cascade
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

  const handleCreateInvoice = async (e) => {
    e.preventDefault();
    try {
      await createInvoiceApi(token, {
        ...formData,
        invoice_date: new Date(formData.invoice_date).toISOString(),
        items: [
          {
            item_name: 'Sample Item',
            unit: 'pcs',
            quantity: 1,
            unit_price: formData.total_amount,
            total_price: formData.total_amount,
            vat_rate: 0,
          },
        ],
      });
      setShowAddForm(false);
      setFormData(EMPTY_FORM);
      loadInvoices();
    } catch (err) {
      setError(err.message);
    }
  };

  const renderStatusStamp = (status) => {
    switch (status) {
      case 'verified':
      case 'approved':
        return <span className="stamp approved">Verified</span>;
      case 'rejected':
        return <span className="stamp rejected">Rejected</span>;
      case 'synced':
        return <span className="stamp synced">Synced</span>;
      case 'pending':
      default:
        return <span className="stamp pending">Pending</span>;
    }
  };

  return (
    <div id="page-invoices" className="page active">
      <div className="page-header">
        <h2>
          <span className="eyebrow">Ledger</span>Invoices
        </h2>
        <button className="btn-seal" onClick={() => setShowAddForm(!showAddForm)}>
          {showAddForm ? '✕ Cancel' : '+ Add Invoice'}
        </button>
      </div>

      <div className="callout">
        <div className="callout-text">
          Scan the inbox for newly arrived invoice emails and queue them here for review.
          {checkMailStatus && <div className="callout-substatus">{checkMailStatus}</div>}
        </div>
        <button className="btn-mail" onClick={handleCheckMail} disabled={checkMailRunning}>
          {checkMailRunning ? '⏳ Checking...' : '✉ Check Mail Now'}
        </button>
      </div>

      {showAddForm && (
        <div className="panel form-panel">
          <h3>Add New Invoice</h3>
          <form onSubmit={handleCreateInvoice} className="add-invoice-form">
            <div className="field">
              <label>Invoice Number</label>
              <input
                type="text"
                required
                value={formData.invoice_number}
                onChange={(e) => setFormData({ ...formData, invoice_number: e.target.value })}
                placeholder="e.g., INV-001"
              />
            </div>
            <div className="form-row">
              <div className="field">
                <label>Invoice Date</label>
                <input
                  type="date"
                  required
                  value={formData.invoice_date}
                  onChange={(e) => setFormData({ ...formData, invoice_date: e.target.value })}
                />
              </div>
              <div className="field">
                <label>Total Amount (VND)</label>
                <input
                  type="number"
                  required
                  min="0"
                  step="0.01"
                  value={formData.total_amount}
                  onChange={(e) => setFormData({ ...formData, total_amount: parseFloat(e.target.value) || 0 })}
                />
              </div>
            </div>
            <div className="field">
              <label>Buyer Name</label>
              <input
                type="text"
                required
                value={formData.buyer_name}
                onChange={(e) => setFormData({ ...formData, buyer_name: e.target.value })}
                placeholder="Enter buyer name"
              />
            </div>
            <div className="form-actions-row">
              <button type="submit" className="btn-seal">Save Invoice</button>
              <button type="button" onClick={() => setShowAddForm(false)} className="btn-ghost">Cancel</button>
            </div>
          </form>
        </div>
      )}

      {error && <div className="alert alert-error">{error}</div>}

      <div className="panel">
        <div className="toolbar">
          <input
            className="search-input"
            placeholder="Search invoices..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          <select
            className="select-input"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All Status</option>
            <option value="pending">Pending</option>
            <option value="verified">Verified</option>
            <option value="rejected">Rejected</option>
            <option value="synced">Synced</option>
          </select>
        </div>

        {loading ? (
          <div className="empty-state">
            <div className="glyph">⏳</div>
            <p>Loading invoices...</p>
          </div>
        ) : invoices.length === 0 ? (
          <div className="empty-state">
            <div className="glyph">▤</div>
            <h3>No invoices found</h3>
            <p>There are no invoices matching your criteria.</p>
          </div>
        ) : (
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
            <tbody id="invoice-tbody">
              {invoices.map((inv) => (
                <tr key={inv.id}>
                  <td data-label="Lookup Code"><span className="code">{inv.lookup_code || '—'}</span></td>
                  <td data-label="Series"><span className="code">{inv.invoice_series || '—'}</span></td>
                  <td data-label="Invoice #"><b>{inv.invoice_number}</b></td>
                  <td data-label="Date">
                    {inv.invoice_date ? new Date(inv.invoice_date).toLocaleDateString('vi-VN') : '—'}
                  </td>
                  <td data-label="Buyer">{inv.buyer_name || '—'}</td>
                  <td data-label="Amount">
                    <span className="amount">{(inv.total_amount || 0).toLocaleString('vi-VN')} VND</span>
                  </td>
                  <td data-label="Status">{renderStatusStamp(inv.status)}</td>
                  <td data-label="Actions">
                    <div className="row-actions">
                      <button className="act" onClick={() => handleViewInvoice(inv.id)}>
                        👁 View
                      </button>
                      {inv.status === 'pending' && (
                        <>
                          <button
                            className="act approve"
                            onClick={() => handleApprove(inv.id)}
                            disabled={isApproving(inv.id)}
                          >
                            {isApproving(inv.id) ? '⏳' : '✓'} Approve
                          </button>
                          <button
                            className="act reject"
                            onClick={() => handleReject(inv.id)}
                            disabled={isRejecting(inv.id)}
                          >
                            {isRejecting(inv.id) ? '⏳' : '✕'} Reject
                          </button>
                        </>
                      )}
                      <button
                        className="act delete"
                        onClick={() => handleOpenDeleteModal(inv)}
                        disabled={isDeleting(inv.id)}
                      >
                        {isDeleting(inv.id) ? '⏳' : '🗑'} Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Delete Modal */}
      {deleteModal.show && (
        <div className="modal-backdrop">
          <div className="login-card modal-card">
            <h3>Delete Invoice #{deleteModal.invoiceNumber}?</h3>
            <p className="help-text">Products in invoice: {deleteModal.productCount}</p>
            <div className="modal-options">
              <button
                className="btn-primary btn-danger-action"
                onClick={() => handleDeleteInvoice(true)}
              >
                Delete Invoice & Revert Inventory
              </button>
              <button
                className="btn-ghost"
                style={{ marginTop: '8px', width: '100%' }}
                onClick={() => handleDeleteInvoice(false)}
              >
                Delete Invoice Only
              </button>
              <button
                className="btn-ghost"
                style={{ marginTop: '8px', width: '100%', borderColor: 'transparent' }}
                onClick={() => setDeleteModal(EMPTY_DELETE_MODAL)}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* View Modal */}
      <InvoiceDetailsModal
        invoice={selectedInvoice}
        onClose={() => setSelectedInvoice(null)}
      />
    </div>
  );
}

export default InvoiceModule;
