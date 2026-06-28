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
    productName: null
  });
  const [formData, setFormData] = useState({
    name: '',
    price: 0,
    quantity_in_stock: 0,
    category: '',
    description: ''
  });

  // Fetch products
  const fetchProducts = useCallback(async () => {
    setLoading(true);
    setError('');
    
    try {
      let url = `${API_BASE}/api/products/?limit=100`;
      if (categoryFilter) url += `&category=${categoryFilter}`;
      if (searchTerm) url += `&search=${searchTerm}`;

      const response = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` }
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

  // Fetch categories
  useEffect(() => {
    const fetchCategories = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/products/categories`, {
          headers: { Authorization: `Bearer ${token}` }
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

  // Subscribe to WebSocket updates
  useEffect(() => {
    const unsubscribe1 = subscribe('notification', (message) => {
      const notif = message.notification;
      // Refetch products on any product/invoice-related notification
      if (notif.type && (
        notif.type.includes('product') || 
        notif.type.includes('invoice_approved')
      )) {
        console.log('Product/invoice update notification:', notif.type);
        fetchProducts();
      }
    });

    return unsubscribe1;
  }, [subscribe, fetchProducts]);

  // Handle open delete modal
  const handleOpenDeleteModal = (product) => {
    setDeleteModal({
      show: true,
      productId: product.id,
      productName: product.name
    });
  };

  // Handle delete product
  const handleDeleteProduct = async () => {
    const { productId, productName } = deleteModal;
    
    try {
      const response = await fetch(`${API_BASE}/api/products/${productId}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to delete product');
      }

      alert(`✅ Product "${productName}" has been deleted`);
      
      // Close modal and refresh
      setDeleteModal({ show: false, productId: null, productName: null });
      fetchProducts();
    } catch (err) {
      setError(err.message);
      setDeleteModal({ show: false, productId: null, productName: null });
    }
  };

  // Handle create product
  const handleCreateProduct = async (e) => {
    e.preventDefault();
    
    try {
      const response = await fetch(`${API_BASE}/api/products/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          ...formData,
          price: parseFloat(formData.price),
          quantity_in_stock: parseInt(formData.quantity_in_stock)
        })
      });

      if (!response.ok) throw new Error('Failed to create product');

      setShowAddForm(false);
      setFormData({
        name: '',
        price: 0,
        quantity_in_stock: 0,
        category: '',
        description: ''
      });
      
      fetchProducts();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="product-module">
      <div className="module-header">
        <h2>📦 Products</h2>
        <button onClick={() => setShowAddForm(!showAddForm)} className="btn-primary">
          {showAddForm ? 'Cancel' : '+ Add Product'}
        </button>
      </div>

      {/* Filters */}
      <div className="filters-section">
        <input
          type="text"
          placeholder="Search products..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="filter-input"
        />
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="filter-select"
        >
          <option value="">All Categories</option>
          {categories.map(cat => (
            <option key={cat} value={cat}>{cat}</option>
          ))}
        </select>
      </div>

      {/* Add Product Form */}
      {showAddForm && (
        <form onSubmit={handleCreateProduct} className="add-form">
          <h3>Add New Product</h3>
          
          <div className="form-group">
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
            <div className="form-group">
              <label>Price *</label>
              <input
                type="number"
                required
                min="0"
                step="0.01"
                value={formData.price}
                onChange={(e) => setFormData({ ...formData, price: parseFloat(e.target.value) })}
              />
            </div>

            <div className="form-group">
              <label>Stock Quantity *</label>
              <input
                type="number"
                required
                min="0"
                value={formData.quantity_in_stock}
                onChange={(e) => setFormData({ ...formData, quantity_in_stock: parseInt(e.target.value) })}
              />
            </div>

            <div className="form-group">
              <label>Category</label>
              <input
                type="text"
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                placeholder="e.g., Electronics"
              />
            </div>
          </div>

          <div className="form-group">
            <label>Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Product details"
              rows="3"
            />
          </div>

          <div className="form-actions">
            <button type="submit" className="btn-primary">Save Product</button>
            <button type="button" onClick={() => setShowAddForm(false)} className="btn-secondary">Cancel</button>
          </div>
        </form>
      )}

      {/* Error Message */}
      {error && <div className="error-message">{error}</div>}

      {/* Loading */}
      {loading && <div className="loading">Loading products...</div>}

      {/* Products Table */}
      {!loading && products.filter(p => p.quantity_in_stock > 0).length === 0 ? (
        <div className="empty-state">
          <p>No active products (all have 0 stock)</p>
        </div>
      ) : (
        <div className="products-table-wrapper">
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
              {products.filter(p => p.quantity_in_stock > 0).map(product => (
                <tr key={product.id}>
                  <td>{product.name}</td>
                  <td>{product.price.toLocaleString('vi-VN')} VND</td>
                  <td>{product.quantity_in_stock}</td>
                  <td>{product.category || '-'}</td>
                  <td>
                    <span className={`badge ${product.quantity_in_stock < 10 ? 'low-stock' : 'in-stock'}`}>
                      {product.quantity_in_stock < 10 ? 'Low' : 'OK'}
                    </span>
                  </td>
                  <td>
                    <button
                      onClick={() => handleOpenDeleteModal(product)}
                      className="btn-delete-product"
                      title="Delete this product"
                    >
                      🗑️ Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteModal.show && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3>🗑️ Delete Product</h3>
            <p><strong>Product Name:</strong> {deleteModal.productName}</p>
            <p className="warning-text">⚠️ This action cannot be undone! This product will be permanently removed from the inventory.</p>
            
            <div className="modal-actions">
              <button
                onClick={handleDeleteProduct}
                className="btn-confirm-delete"
              >
                🗑️ Confirm Delete
              </button>
              <button
                onClick={() => setDeleteModal({ show: false, productId: null, productName: null })}
                className="btn-cancel-delete"
              >
                ❌ Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ProductModule;
