import React, { useState } from 'react';
import './InvoiceDetailsModal.css';

const STATUS_LABELS = {
  pending: '⏳ Pending',
  verified: '✅ Verified',
  rejected: '❌ Rejected',
  synced: '📤 Synced',
};

function InvoiceDetailsModal({ invoice, onClose }) {
  const [showRawJson, setShowRawJson] = useState(false);

  if (!invoice) return null;

  const formatDate = (dateString) => {
    if (!dateString) return '—';
    return new Date(dateString).toLocaleDateString('vi-VN');
  };

  const formatCurrency = (amount) => {
    if (amount === null || amount === undefined) return '0 VND';
    return `${amount.toLocaleString('vi-VN')} VND`;
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content invoice-details-modal">
        
        {/* Header */}
        <div className="invoice-header">
          <div className="header-title">
            <h2>Invoice {invoice.invoice_number}</h2>
            <span className={`badge badge-${invoice.status}`}>
              {STATUS_LABELS[invoice.status] ?? invoice.status}
            </span>
            {invoice.ai_confidence > 0 && (
              <span className={`badge confidence-${invoice.ai_confidence >= 80 ? 'high' : 'medium'}`}>
                🤖 AI Confidence: {invoice.ai_confidence}%
              </span>
            )}
          </div>
          <div className="header-actions">
            <button 
              onClick={() => window.open(`/api/invoices/${invoice.id}/file`, '_blank')} 
              className="btn-view-file"
              title="View Original File"
            >
              📄 View File
            </button>
            <button onClick={onClose} className="btn-close">❌</button>
          </div>
        </div>

        <div className="invoice-body">
          {/* Top Meta Info */}
          <div className="meta-info-bar">
            <span><strong>Date:</strong> {formatDate(invoice.invoice_date)}</span>
            <span><strong>Lookup Code:</strong> {invoice.lookup_code || '—'}</span>
            <span><strong>Tax Auth Code:</strong> {invoice.tax_authority_code || '—'}</span>
            <span><strong>Source:</strong> {invoice.source_email || '—'}</span>
          </div>

          {/* Parties Section */}
          <div className="parties-section">
            <div className="party-card seller-card">
              <h3>🏢 Seller Details</h3>
              <p><strong>Name:</strong> {invoice.seller_name || '—'}</p>
              <p><strong>Tax Code:</strong> {invoice.seller_tax_code || '—'}</p>
              <p><strong>Address:</strong> {invoice.seller_address || '—'}</p>
              <p><strong>Phone:</strong> {invoice.seller_phone || '—'}</p>
            </div>
            
            <div className="party-card buyer-card">
              <h3>👤 Buyer Details</h3>
              <p><strong>Name:</strong> {invoice.buyer_name || '—'}</p>
              <p><strong>Tax Code:</strong> {invoice.buyer_tax_code || '—'}</p>
              <p><strong>Address:</strong> {invoice.buyer_address || '—'}</p>
            </div>
          </div>

          {/* Line Items Table */}
          <div className="items-section">
            <h3>📦 Line Items ({invoice.items?.length || 0})</h3>
            <div className="table-responsive">
              <table className="items-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Product / Service</th>
                    <th>Unit</th>
                    <th className="text-right">Qty</th>
                    <th className="text-right">Unit Price</th>
                    <th className="text-right">VAT %</th>
                    <th className="text-right">Total Price</th>
                  </tr>
                </thead>
                <tbody>
                  {invoice.items && invoice.items.length > 0 ? (
                    invoice.items.map((item, index) => (
                      <tr key={item.id || index}>
                        <td>{item.line_number || index + 1}</td>
                        <td className="item-name">{item.item_name}</td>
                        <td>{item.unit || '—'}</td>
                        <td className="text-right">{item.quantity}</td>
                        <td className="text-right">{formatCurrency(item.unit_price)}</td>
                        <td className="text-right">{item.vat_rate}%</td>
                        <td className="text-right"><strong>{formatCurrency(item.total_price)}</strong></td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="7" className="text-center">No items found</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Totals Section */}
          <div className="totals-section">
            <div className="totals-box">
              <div className="total-row">
                <span>Total Before Tax:</span>
                <span>{formatCurrency(invoice.total_before_tax)}</span>
              </div>
              <div className="total-row">
                <span>VAT Amount:</span>
                <span>{formatCurrency(invoice.vat_amount)}</span>
              </div>
              <div className="total-row grand-total">
                <span>Grand Total:</span>
                <span>{formatCurrency(invoice.total_amount)}</span>
              </div>
            </div>
          </div>

          {/* Developer / Raw JSON Section */}
          <div className="raw-json-section">
            <button 
              className="btn-toggle-json"
              onClick={() => setShowRawJson(!showRawJson)}
            >
              {showRawJson ? '▼ Hide Raw Data' : '▶ View Raw JSON Data'}
            </button>
            
            {showRawJson && (
              <pre className="json-viewer">
                {JSON.stringify(invoice, null, 2)}
              </pre>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default InvoiceDetailsModal;
