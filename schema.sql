-- Tool ORC Invoice Database Schema - Enhanced Vietnamese Invoice Structure with Audit Logging

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT False,
    is_admin BOOLEAN DEFAULT False,
    telegram_auth_msg_id VARCHAR(50),
    -- Credentials for email and integrations (only used by admin)
    email_password VARCHAR(255),
    gemini_api_key VARCHAR(500),
    telegram_bot_token VARCHAR(500),
    telegram_chat_id VARCHAR(100),
    imap_server VARCHAR(100),
    smtp_server VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit Log table (for security and access control)
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,  -- LOGIN, API_ACCESS, CREATE, UPDATE, DELETE, etc.
    resource VARCHAR(50),  -- INVOICE, USER, PRODUCT, etc.
    resource_id INT,
    details TEXT,
    status_code INT DEFAULT 200,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),  -- IPv4 or IPv6
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Products table
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    sku VARCHAR(100),
    barcode VARCHAR(100),
    price DECIMAL(10, 2) NOT NULL,
    quantity_in_stock INT DEFAULT 0,
    category VARCHAR(100),
    supplier VARCHAR(200),
    image_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Invoices table (Enhanced for Vietnamese e-invoices)
CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    
    -- Invoice Identification
    invoice_series VARCHAR(50),  -- Ký hiệu hóa đơn (e.g., "1C26TBN")
    invoice_number VARCHAR(50) NOT NULL,  -- Số hóa đơn (e.g., "00000014")
    full_invoice_number VARCHAR(100) UNIQUE,  -- Full: series/number
    invoice_date TIMESTAMP,
    
    -- Lookup & Tax Authority Codes
    lookup_code VARCHAR(100),  -- Mã tra cứu (e.g., "232651001C26TBN14547837")
    tax_authority_code VARCHAR(100),  -- Mã CQ Thuế
    
    -- Seller Information
    seller_name VARCHAR(255),
    seller_tax_code VARCHAR(50),
    seller_phone VARCHAR(20),
    seller_address TEXT,
    
    -- Buyer Information
    buyer_name VARCHAR(255),
    buyer_tax_code VARCHAR(50),
    buyer_address TEXT,
    
    -- Financial Information
    total_before_tax DECIMAL(12, 2) DEFAULT 0,
    vat_rate DECIMAL(5, 2) DEFAULT 0,
    vat_amount DECIMAL(12, 2) DEFAULT 0,
    total_amount DECIMAL(12, 2) DEFAULT 0,
    
    -- Processing Information
    status VARCHAR(20) DEFAULT 'pending',  -- pending, verified, synced
    user_id INT REFERENCES users(id) ON DELETE SET NULL,
    source_email VARCHAR(255),
    source_type VARCHAR(50),  -- email_attachment, email_link, portal_download
    raw_file_path TEXT,  -- Path to original PDF/XML
    file_format VARCHAR(20),  -- pdf, xml
    ai_confidence DECIMAL(5, 2) DEFAULT 0,  -- 0-100 confidence score
    
    -- Signature Information (JSON)
    signatures JSONB,  -- Contains seller and tax authority signatures
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

-- Invoice Items table (Enhanced)
CREATE TABLE IF NOT EXISTS invoice_items (
    id SERIAL PRIMARY KEY,
    invoice_id INT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    product_id INT REFERENCES products(id) ON DELETE SET NULL,
    
    -- Item Details
    item_name VARCHAR(500) NOT NULL,  -- Full product name (e.g., "Lưới bóng đá khung thành mini...")
    unit VARCHAR(50),  -- Unit (Cặp, Túi, Cái, etc.)
    quantity DECIMAL(10, 2) NOT NULL,
    unit_price DECIMAL(12, 2) NOT NULL,
    total_price DECIMAL(12, 2) NOT NULL,
    vat_rate DECIMAL(5, 2) DEFAULT 0,
    
    -- Order tracking
    line_number INT,  -- Position in invoice
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Invoice Notifications table
CREATE TABLE IF NOT EXISTS invoice_notifications (
    id SERIAL PRIMARY KEY,
    invoice_id INT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    bot_token VARCHAR(500) NOT NULL,
    chat_id VARCHAR(100) NOT NULL,
    message_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Email Logs table
CREATE TABLE IF NOT EXISTS email_logs (
    id SERIAL PRIMARY KEY,
    invoice_id INT REFERENCES invoices(id) ON DELETE SET NULL,
    email_from VARCHAR(255),
    email_subject VARCHAR(500),
    attachment_name VARCHAR(255),
    file_url TEXT,
    message_id VARCHAR(255) UNIQUE,
    status VARCHAR(50) DEFAULT 'pending',  -- pending, processing, success, error
    error_message TEXT,
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Signatures table (for detailed signature information)
CREATE TABLE IF NOT EXISTS signatures (
    id SERIAL PRIMARY KEY,
    invoice_id INT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    signer_name VARCHAR(255),
    signer_role VARCHAR(100),  -- seller, tax_authority
    signature_date TIMESTAMP,
    certificate_cn VARCHAR(500),  -- For tax authority (CN=...)
    is_valid BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Inventory Audit Log table (tracks product inventory changes)
CREATE TABLE IF NOT EXISTS inventory_audit_logs (
    id SERIAL PRIMARY KEY,
    product_id INT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    invoice_id INT REFERENCES invoices(id) ON DELETE CASCADE,
    
    -- Change details
    action VARCHAR(50) NOT NULL,  -- "add", "update", "approve_invoice", "revert"
    quantity_change INT NOT NULL,  -- How much was added/changed
    old_quantity INT NOT NULL,  -- Quantity before change
    new_quantity INT NOT NULL,  -- Quantity after change
    old_price DECIMAL(10, 2),  -- Price before change
    new_price DECIMAL(10, 2),  -- Price after change
    
    -- Metadata
    reason TEXT,  -- Why the change was made
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_invoices_invoice_number ON invoices(invoice_number);
CREATE INDEX idx_invoices_full_invoice_number ON invoices(full_invoice_number);
CREATE INDEX idx_invoices_user_id ON invoices(user_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_source_email ON invoices(source_email);
CREATE INDEX idx_invoices_invoice_date ON invoices(invoice_date);
CREATE INDEX idx_invoice_items_invoice_id ON invoice_items(invoice_id);
CREATE INDEX idx_email_logs_invoice_id ON email_logs(invoice_id);
CREATE INDEX idx_email_logs_status ON email_logs(status);
CREATE INDEX idx_signatures_invoice_id ON signatures(invoice_id);
CREATE INDEX idx_inventory_audit_logs_product_id ON inventory_audit_logs(product_id);
CREATE INDEX idx_inventory_audit_logs_invoice_id ON inventory_audit_logs(invoice_id);
CREATE INDEX idx_inventory_audit_logs_created_at ON inventory_audit_logs(created_at);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource, resource_id);


