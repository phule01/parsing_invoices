import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useWebSocket } from '../../context/WebSocketContext';
import './ProductModule.css';

const API_BASE = process.env.REACT_APP_API_URL || (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : '');

function ProductModule() {
  const { token } = useAuth();
  const { subscribe } = useWebSocket();
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [categories, setCategories] = useState([]);
  const [showAddForm, setShowAddForm] = useState(false);
  const [deleteModal, setDeleteModal] = useState({
    show: false,
    productId: null,
    productName: null,
  });
  const [formData, setFormData] = useState({
    name: '',
    price: 0,
    quantity_in_stock: 0,
    category: '',
    description: '',
  });

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      let url = `${API_BASE}/api/products/?limit=100`;
      if (categoryFilter) url += `&category=${categoryFilter}`;
      if (searchTerm) url += `&search=${searchTerm}`;

      const response = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) throw new Error('Failed to fetch products');

      const data = await response.json();
      setProducts(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, categoryFilter, searchTerm]);

  useEffect(() => {
    const fetchCategories = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/products/categories`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (response.ok) {
          const data = await response.json();
          setCategories(data.categories || []);
        }
      } catch (err) {
        console.error('Failed to fetch categories:', err);
      }
    };

    fetchCategories();
  }, [token]);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  useEffect(() => {
    const unsubscribe1 = subscribe('notification', (message) => {
      const notif = message.notification;
      if (
        notif.type &&
        (notif.type.includes('product') || notif.type.includes('invoice_approved'))
      ) {
        fetchProducts();
      }
    });

    return unsubscribe1;
  }, [subscribe, fetchProducts]);

  const handleOpenDeleteModal = (product) => {
    setDeleteModal({
      show: true,
      productId: product.id,
      productName: product.name,
    });
  };

  const handleDeleteProduct = async () => {
    const { productId, productName } = deleteModal;

    try {
      const response = await fetch(`${API_BASE}/api/products/${productId}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to delete product');
      }

      alert(`✅ Product "${productName}" has been deleted`);
      setDeleteModal({ show: false, productId: null, productName: null });
      fetchProducts();
    } catch (err) {
      setError(err.message);
      setDeleteModal({ show: false, productId: null, productName: null });
    }
  };

  const handleCreateProduct = async (e) => {
    e.preventDefault();

    try {
      const response = await fetch(`${API_BASE}/api/products/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          ...formData,
          price: parseFloat(formData.price) || 0,
          quantity_in_stock: parseInt(formData.quantity_in_stock) || 0,
        }),
      });

      if (!response.ok) throw new Error('Failed to create product');

      setShowAddForm(false);
      setFormData({
        name: '',
        price: 0,
        quantity_in_stock: 0,
        category: '',
        description: '',
      });

      fetchProducts();
    } catch (err) {
      setError(err.message);
    }
  };

  const activeProducts = products.filter((p) => p.quantity_in_stock > 0);

  return (
    <div id="page-products" className="page active">
      <div className="page-header">
        <h2>
          <span className="eyebrow">Inventory</span>Products
        </h2>
        <button className="btn-seal" onClick={() => setShowAddForm(!showAddForm)}>
          {showAddForm ? '✕ Cancel' : '+ Add Product'}
        </button>
      </div>

      {showAddForm && (
        <div className="panel form-panel">
          <h3>Add New Product</h3>
          <form onSubmit={handleCreateProduct} className="add-product-form">
            <div className="field">
              <label>Product Name *</label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., USB Cable"
              />
            </div>

            <div className="form-row">
              <div className="field">
                <label>Price (VND) *</label>
                <input
                  type="number"
                  required
                  min="0"
                  step="0.01"
                  value={formData.price}
                  onChange={(e) => setFormData({ ...formData, price: e.target.value })}
                />
              </div>

              <div className="field">
                <label>Stock Quantity *</label>
                <input
                  type="number"
                  required
                  min="0"
                  value={formData.quantity_in_stock}
                  onChange={(e) => setFormData({ ...formData, quantity_in_stock: e.target.value })}
                />
              </div>

              <div className="field">
                <label>Category</label>
                <input
                  type="text"
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                  placeholder="e.g., Electronics"
                />
              </div>
            </div>

            <div className="field">
              <label>Description</label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Product details"
                rows="3"
              />
            </div>

            <div className="form-actions-row">
              <button type="submit" className="btn-seal">Save Product</button>
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
            placeholder="Search products..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          <select
            className="select-input"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
          >
            <option value="">All Categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>

        {loading ? (
          <div className="empty-state">
            <div className="glyph">⏳</div>
            <p>Loading inventory...</p>
          </div>
        ) : activeProducts.length === 0 ? (
          <div className="empty-state">
            <div className="glyph">▣</div>
            <h3>No products in stock</h3>
            <p>Every item on hand currently reads zero. Add a product to start tracking it here.</p>
          </div>
        ) : (
          <table className="products-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Price</th>
                <th>Stock</th>
                <th>Category</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {activeProducts.map((product) => (
                <tr key={product.id}>
                  <td data-label="Name"><b>{product.name}</b></td>
                  <td data-label="Price">
                    <span className="amount">{(product.price || 0).toLocaleString('vi-VN')} VND</span>
                  </td>
                  <td data-label="Stock"><span className="code">{product.quantity_in_stock}</span></td>
                  <td data-label="Category">{product.category || '—'}</td>
                  <td data-label="Status">
                    <span className={`stamp ${product.quantity_in_stock < 10 ? 'rejected' : 'approved'}`}>
                      {product.quantity_in_stock < 10 ? 'Low Stock' : 'In Stock'}
                    </span>
                  </td>
                  <td data-label="Actions">
                    <button
                      className="act delete"
                      onClick={() => handleOpenDeleteModal(product)}
                    >
                      🗑 Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {deleteModal.show && (
        <div className="modal-backdrop">
          <div className="login-card modal-card">
            <h3>Delete Product?</h3>
            <p className="help-text">Product: <b>{deleteModal.productName}</b></p>
            <p className="help-text" style={{ color: 'var(--seal)' }}>⚠️ Action cannot be undone.</p>
            <div className="modal-options" style={{ marginTop: '16px' }}>
              <button className="btn-primary btn-danger-action" onClick={handleDeleteProduct}>
                Confirm Delete
              </button>
              <button
                className="btn-ghost"
                style={{ marginTop: '8px', width: '100%' }}
                onClick={() => setDeleteModal({ show: false, productId: null, productName: null })}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ProductModule;
