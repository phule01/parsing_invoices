import os
import logging
import pymysql
from datetime import datetime

logger = logging.getLogger(__name__)

def _get_connection():
    """Get a connection to the MySQL database."""
    try:
        return pymysql.connect(
            host=os.getenv("MYSQL_HOST", "mysql_db"),
            port=int(os.getenv("MYSQL_PORT", 3306)),
            user=os.getenv("MYSQL_USER", "mysql"),
            password=os.getenv("MYSQL_PASSWORD", "mysql"),
            database=os.getenv("MYSQL_DB", "tool_orc_sync_db"),
            cursorclass=pymysql.cursors.DictCursor
        )
    except Exception as e:
        logger.error(f"❌ Failed to connect to MySQL: {e}")
        return None

def _create_tables_if_not_exist(conn):
    """Ensure the sync tables exist in MySQL."""
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS synced_invoices (
                id INT PRIMARY KEY,
                invoice_number VARCHAR(50) NOT NULL,
                invoice_series VARCHAR(50),
                invoice_date DATETIME,
                seller_name VARCHAR(255),
                buyer_name VARCHAR(255),
                total_amount DECIMAL(12, 2),
                status VARCHAR(20),
                synced_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS synced_invoice_items (
                id INT PRIMARY KEY,
                invoice_id INT NOT NULL,
                item_name VARCHAR(500) NOT NULL,
                quantity DECIMAL(10, 2),
                unit_price DECIMAL(10, 2),
                total_price DECIMAL(12, 2),
                FOREIGN KEY (invoice_id) REFERENCES synced_invoices(id) ON DELETE CASCADE
            )
        """)
    conn.commit()

def sync_invoice_to_mysql(invoice_data: dict) -> bool:
    """
    Sync a single invoice and its items to MySQL.
    Can be called as a Background Task in FastAPI.
    Accepts a dictionary to avoid SQLAlchemy DetachedInstanceError.
    """
    conn = _get_connection()
    if not conn:
        return False
        
    try:
        _create_tables_if_not_exist(conn)
        
        with conn.cursor() as cursor:
            # Upsert invoice
            cursor.execute("""
                INSERT INTO synced_invoices 
                (id, invoice_number, invoice_series, invoice_date, seller_name, buyer_name, total_amount, status, synced_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                invoice_number=VALUES(invoice_number),
                invoice_series=VALUES(invoice_series),
                invoice_date=VALUES(invoice_date),
                seller_name=VALUES(seller_name),
                buyer_name=VALUES(buyer_name),
                total_amount=VALUES(total_amount),
                status=VALUES(status),
                synced_at=VALUES(synced_at)
            """, (
                invoice_data.get("id"),
                invoice_data.get("invoice_number"),
                invoice_data.get("invoice_series"),
                invoice_data.get("invoice_date"),
                invoice_data.get("seller_name"),
                invoice_data.get("buyer_name"),
                invoice_data.get("total_amount"),
                invoice_data.get("status"),
                datetime.utcnow()
            ))
            
            # Delete existing items for this invoice
            cursor.execute("DELETE FROM synced_invoice_items WHERE invoice_id = %s", (invoice_data.get("id"),))
            
            # Insert items
            for item in invoice_data.get('items', []):
                cursor.execute("""
                    INSERT INTO synced_invoice_items 
                    (id, invoice_id, item_name, quantity, unit_price, total_price)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    item.get("id"),
                    invoice_data.get("id"),
                    item.get("item_name"),
                    item.get("quantity"),
                    item.get("unit_price"),
                    item.get("total_price")
                ))
                
        conn.commit()
        logger.info(f"✅ Successfully synced invoice {invoice_data.get('invoice_number')} to MySQL")
        return True
    except Exception as e:
        logger.error(f"❌ Error syncing invoice {invoice_data.get('invoice_number')} to MySQL: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
