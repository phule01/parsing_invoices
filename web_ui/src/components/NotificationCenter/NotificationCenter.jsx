import React, { useState, useEffect } from 'react';
import { useWebSocket } from '../../context/WebSocketContext';
import { useInvoiceActions } from '../../hooks/useInvoiceActions';
import './NotificationCenter.css';

function NotificationCenter() {
  const { subscribe } = useWebSocket();
  const { approve, reject, isApproving, isRejecting } = useInvoiceActions();
  const [notifications, setNotifications] = useState([]);

  useEffect(() => {
    return subscribe('notification', (message) => {
      const id = `${Date.now()}-${Math.random()}`;
      const notif = { id, ...message.notification };
      setNotifications((prev) => [notif, ...prev]);
      const ttl = notif.action_required ? 12_000 : 6_000;
      setTimeout(() => {
        setNotifications((prev) => prev.filter((n) => n.id !== id));
      }, ttl);
    });
  }, [subscribe]);

  const dismiss = (id) =>
    setNotifications((prev) => prev.filter((n) => n.id !== id));

  const handleApprove = async (invoiceId, notifId) => {
    try {
      await approve(invoiceId, () => dismiss(notifId));
    } catch {
      // non-conflict errors shown via hook.error
    }
  };

  const handleReject = async (invoiceId, notifId) => {
    try {
      await reject(invoiceId, () => dismiss(notifId));
    } catch {
      // same
    }
  };

  if (notifications.length === 0) return null;

  return (
    <div className="notification-container">
      {notifications.map((notif) => (
        <Notification
          key={notif.id}
          notif={notif}
          onDismiss={dismiss}
          onApprove={handleApprove}
          onReject={handleReject}
          isApproving={isApproving(notif.invoice_id)}
          isRejecting={isRejecting(notif.invoice_id)}
        />
      ))}
    </div>
  );
}

// ── Presentational sub-component ──────────────────────────────────────────────

function severityIcon(type, severity) {
  if (type?.includes('success') || type?.includes('approved') || type?.includes('deleted')) return '✅';
  if (type?.includes('error') || type?.includes('failed') || type?.includes('rejected')) return '❌';
  if (type === 'invoice_received') return '📬';
  if (severity === 'error') return '❌';
  if (severity === 'warning') return '⚠️';
  if (severity === 'success') return '✅';
  return 'ℹ️';
}

function Notification({ notif, onDismiss, onApprove, onReject, isApproving, isRejecting }) {
  const busy = isApproving || isRejecting;
  const showActions = notif.action_required && notif.type === 'invoice_received';

  return (
    <div className={[
      'notification',
      `notification-${notif.severity || 'info'}`,
      notif.action_required ? 'action-required' : '',
    ].filter(Boolean).join(' ')}>
      <div className="notification-content">
        <div className="notification-header">
          <span className="notification-icon">{severityIcon(notif.type, notif.severity)}</span>
          <span className="notification-title">{notif.title}</span>
          <button className="notification-close" onClick={() => onDismiss(notif.id)}>×</button>
        </div>
        <div className="notification-message">{notif.message}</div>
        {showActions && (
          <div className="notification-actions">
            <button
              className="action-btn approve-btn"
              onClick={() => onApprove(notif.invoice_id, notif.id)}
              disabled={busy}
            >
              {isApproving ? '⏳ Approving...' : '✅ Approve'}
            </button>
            <button
              className="action-btn reject-btn"
              onClick={() => onReject(notif.invoice_id, notif.id)}
              disabled={busy}
            >
              {isRejecting ? '⏳ Rejecting...' : '❌ Reject'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default NotificationCenter;
