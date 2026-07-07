import asyncio
import os
from unittest.mock import patch, MagicMock

# Setup environment to load FastAPI properly
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/tool_orc_db"

def mock_post(*args, **kwargs):
    url = args[0]
    print(f"MOCK POST to: {url}")
    print(f"Payload: {kwargs.get('json', {})}")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True, "result": {"message_id": 999}}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp

async def main():
    import sys
    sys.path.append("/home/zt/Documents/parsing_invoices/fast_app")
    
    from database import SessionLocal, Base, engine
    from models import User, Invoice, InvoiceNotification
    
    # 1. Setup Data
    db = SessionLocal()
    
    # Create Admin
    admin = db.query(User).filter(User.username == "testadmin").first()
    if not admin:
        admin = User(username="testadmin", hashed_password="pw", is_active=True, is_admin=True,
                     telegram_bot_token="ADMIN_TOKEN", telegram_chat_id="ADMIN_CHAT")
        db.add(admin)
        
    # Create Standard User
    standard = db.query(User).filter(User.username == "teststd").first()
    if not standard:
        standard = User(username="teststd", hashed_password="pw", is_active=True, is_admin=False,
                        telegram_bot_token="STD_TOKEN", telegram_chat_id="STD_CHAT")
        db.add(standard)
        
    # Create an invoice
    inv = Invoice(invoice_number="INV123", total_amount=1000)
    db.add(inv)
    db.commit()
    
    # 2. Test Notification Broadcast
    from app.services.telegram_service import send_invoice_approval_request
    
    print("\n--- Testing Broadcast ---")
    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        await send_invoice_approval_request(
            invoice_id=inv.id,
            invoice_number="INV123",
            seller_name="Test Seller",
            total_amount=1000,
        )
        
    # Check if InvoiceNotifications were created
    notifs = db.query(InvoiceNotification).filter(InvoiceNotification.invoice_id == inv.id).all()
    print(f"Created {len(notifs)} InvoiceNotifications")
    for n in notifs:
        print(f"  -> user_id={n.user_id}, bot={n.bot_token}, chat={n.chat_id}, msg={n.message_id}")
        
    # 3. Test Syncing
    from app.services.telegram_service import sync_invoice_notifications
    print("\n--- Testing Sync ---")
    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        await sync_invoice_notifications(inv.id, "Approved by Admin!")
        
    db.close()

if __name__ == "__main__":
    asyncio.run(main())
