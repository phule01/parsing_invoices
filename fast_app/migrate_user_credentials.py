"""
Migration script to add new credential columns to users table.
Run this once when deploying the updated schema.
"""
from sqlalchemy import text
from database import engine

def migrate():
    """Add new columns to users table if they don't exist."""
    with engine.connect() as conn:
        # Check if columns exist and add them if they don't
        columns_to_add = [
            ("is_admin", "BOOLEAN DEFAULT FALSE"),
            ("email_password", "VARCHAR(255)"),
            ("gemini_api_key", "VARCHAR(500)"),
            ("telegram_bot_token", "VARCHAR(500)"),
            ("telegram_chat_id", "VARCHAR(100)"),
            ("imap_server", "VARCHAR(100)"),
            ("smtp_server", "VARCHAR(100)"),
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
                print(f"✅ Added column: {col_name}")
            except Exception as e:
                if "already exists" in str(e) or "duplicate column" in str(e):
                    print(f"⏭️  Column {col_name} already exists, skipping")
                else:
                    print(f"⚠️  Error adding {col_name}: {e}")
        
        conn.commit()

if __name__ == "__main__":
    print("🔄 Running migration...")
    migrate()
    print("✅ Migration complete!")
