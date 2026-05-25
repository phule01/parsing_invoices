/**
 * invoiceApi.js
 *
 * All invoice-related HTTP calls live here.
 * Components and hooks import functions, never raw fetch() calls or URL strings.
 *
 * Previously these calls were duplicated across:
 *   - InvoiceModule.jsx  (handleApproveInvoice, handleRejectInvoice, handleDeleteInvoice)
 *   - NotificationCenter.jsx (handleApproveInvoice, handleRejectInvoice)
 *
 * Any change to the base URL, headers, or error shape now happens once.
 */

const BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/** @param {string} token */
const authHeaders = (token) => ({
  'Content-Type': 'application/json',
  Authorization: `Bearer ${token}`,
});

/**
 * Parse a response, returning the JSON body.
 * Throws a structured error on non-2xx so callers get a consistent shape.
 * @param {Response} res
 */
async function parseResponse(res) {
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const error = new Error(
      body?.detail?.message || body?.message || body?.detail || 'Request failed'
    );
    error.status = res.status;
    error.body = body;
    throw error;
  }
  return body;
}

// ── List / Get ────────────────────────────────────────────────────────────────

/**
 * @param {string} token
 * @param {{ status?: string, search?: string, skip?: number, limit?: number }} params
 */
export async function fetchInvoices(token, { status, search, skip = 0, limit = 100 } = {}) {
  const url = new URL(`${BASE}/api/invoices/`);
  if (status) url.searchParams.set('status', status);
  if (search) url.searchParams.set('search', search);
  url.searchParams.set('skip', skip);
  url.searchParams.set('limit', limit);

  const res = await fetch(url.toString(), { headers: authHeaders(token) });
  return parseResponse(res);
}

/**
 * @param {string} token
 * @param {number} invoiceId
 */
export async function fetchInvoice(token, invoiceId) {
  const res = await fetch(`${BASE}/api/invoices/${invoiceId}`, {
    headers: authHeaders(token),
  });
  return parseResponse(res);
}

// ── Actions ───────────────────────────────────────────────────────────────────

/**
 * @param {string} token
 * @param {number} invoiceId
 * @returns {Promise<{ status: string, message: string, product_updates: Array }>}
 */
export async function approveInvoice(token, invoiceId) {
  const res = await fetch(`${BASE}/api/invoices/${invoiceId}/approve`, {
    method: 'POST',
    headers: authHeaders(token),
  });
  return parseResponse(res);
}

/**
 * @param {string} token
 * @param {number} invoiceId
 * @returns {Promise<{ status: string, message: string }>}
 */
export async function rejectInvoice(token, invoiceId) {
  const res = await fetch(`${BASE}/api/invoices/${invoiceId}/reject`, {
    method: 'POST',
    headers: authHeaders(token),
  });
  return parseResponse(res);
}

/**
 * @param {string} token
 * @param {number} invoiceId
 * @param {{ cascade?: boolean }} options
 */
export async function deleteInvoice(token, invoiceId, { cascade = false } = {}) {
  const url = `${BASE}/api/invoices/${invoiceId}?cascade_delete=${cascade}`;
  const res = await fetch(url, {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  return parseResponse(res);
}

// ── Create ────────────────────────────────────────────────────────────────────

/**
 * @param {string} token
 * @param {object} payload  — matches InvoiceCreate schema
 */
export async function createInvoice(token, payload) {
  const res = await fetch(`${BASE}/api/invoices/`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
  return parseResponse(res);
}

// ── Email scan ────────────────────────────────────────────────────────────────

/**
 * @param {string} token
 * @param {'unseen' | 'all'} mode
 */
export async function triggerEmailScan(token, mode = 'unseen') {
  const res = await fetch(`${BASE}/api/emails/scan-now?mode=${mode}`, {
    method: 'POST',
    headers: authHeaders(token),
  });
  return parseResponse(res);
}
