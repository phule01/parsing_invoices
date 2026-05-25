"""
Email Listener Service Entry Point
Monitors mailbox and processes invoices from emails using AI parsing
"""

import asyncio
from email_processor import main

if __name__ == "__main__":
    asyncio.run(main())
