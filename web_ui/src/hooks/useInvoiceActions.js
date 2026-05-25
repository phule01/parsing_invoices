/**
 * useInvoiceActions.js
 *
 * Centralises the approve / reject / delete actions that were previously
 * duplicated between InvoiceModule.jsx and NotificationCenter.jsx.
 *
 * Each action follows the same pattern:
 *   1. Set a per-invoice loading key so the UI can disable the correct button.
 *   2. Call the API module (never fetch directly).
 *   3. On success: call the optional onSuccess callback so the parent can
 *      refresh its list or dismiss the notification.
 *   4. On conflict (409): surface a human-readable message without throwing.
 *   5. On any other error: surface the message and re-throw so callers can
 *      log or display it as they see fit.
 *   6. Always clear the loading key in the finally block.
 */

import { useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { approveInvoice, rejectInvoice, deleteInvoice } from '../api/invoiceApi';

/**
 * @typedef {Object} InvoiceActionsHook
 * @property {(invoiceId: number, onSuccess?: () => void) => Promise<void>} approve
 * @property {(invoiceId: number, onSuccess?: () => void) => Promise<void>} reject
 * @property {(invoiceId: number, opts: DeleteOptions, onSuccess?: () => void) => Promise<void>} remove
 * @property {(invoiceId: number) => boolean} isApproving
 * @property {(invoiceId: number) => boolean} isRejecting
 * @property {(invoiceId: number) => boolean} isDeleting
 * @property {string | null} error
 * @property {() => void} clearError
 */

/**
 * @typedef {{ cascade?: boolean }} DeleteOptions
 */

/**
 * @returns {InvoiceActionsHook}
 */
export function useInvoiceActions() {
  const { token } = useAuth();

  // Track which invoice ID is currently being processed per action type.
  // Using a Set lets multiple invoices be processed concurrently if needed.
  const [approving, setApproving] = useState(/** @type {Set<number>} */ (new Set()));
  const [rejecting, setRejecting] = useState(/** @type {Set<number>} */ (new Set()));
  const [deleting,  setDeleting]  = useState(/** @type {Set<number>} */ (new Set()));
  const [error, setError] = useState(/** @type {string|null} */ (null));

  const addId    = (setter, id) => setter(prev => new Set([...prev, id]));
  const removeId = (setter, id) => setter(prev => { const s = new Set(prev); s.delete(id); return s; });

  // ── Approve ─────────────────────────────────────────────────────────────────

  const approve = useCallback(async (invoiceId, onSuccess) => {
    setError(null);
    addId(setApproving, invoiceId);
    try {
      await approveInvoice(token, invoiceId);
      onSuccess?.();
    } catch (err) {
      if (err.status === 409) {
        const processedBy = err.body?.detail?.processed_by ?? 'another session';
        setError(`Invoice already processed by ${processedBy}.`);
        onSuccess?.(); // treat as handled — dismiss the notification
      } else {
        setError(err.message);
        throw err;
      }
    } finally {
      removeId(setApproving, invoiceId);
    }
  }, [token]);

  // ── Reject ───────────────────────────────────────────────────────────────────

  const reject = useCallback(async (invoiceId, onSuccess) => {
    setError(null);
    addId(setRejecting, invoiceId);
    try {
      await rejectInvoice(token, invoiceId);
      onSuccess?.();
    } catch (err) {
      if (err.status === 409) {
        const processedBy = err.body?.detail?.processed_by ?? 'another session';
        setError(`Invoice already processed by ${processedBy}.`);
        onSuccess?.();
      } else {
        setError(err.message);
        throw err;
      }
    } finally {
      removeId(setRejecting, invoiceId);
    }
  }, [token]);

  // ── Delete ────────────────────────────────────────────────────────────────────

  const remove = useCallback(async (invoiceId, { cascade = false } = {}, onSuccess) => {
    setError(null);
    addId(setDeleting, invoiceId);
    try {
      await deleteInvoice(token, invoiceId, { cascade });
      onSuccess?.();
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      removeId(setDeleting, invoiceId);
    }
  }, [token]);

  // ── Helpers ───────────────────────────────────────────────────────────────────

  return {
    approve,
    reject,
    remove,
    isApproving: (id) => approving.has(id),
    isRejecting: (id) => rejecting.has(id),
    isDeleting:  (id) => deleting.has(id),
    error,
    clearError: () => setError(null),
  };
}
