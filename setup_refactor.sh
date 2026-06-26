#!/bin/bash
# setup_refactor.sh
#
# Run this from the PROJECT ROOT (the directory that contains docker-compose.yml).
# It creates the new package skeleton inside fastapi_app/ and copies every
# refactored file from the downloaded outputs into the right location.
#
# Usage:
#   chmod +x setup_refactor.sh
#   ./setup_refactor.sh
#
# After running:
#   DEV  → docker compose restart fastapi
#   PROD → docker compose -f docker-compose.prod.yml build fastapi
#          docker compose -f docker-compose.prod.yml up -d fastapi

set -e

FASTAPI=./fastapi_app
OUTPUTS=./refactor_outputs   # folder where you put the downloaded files

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 1 — Create new package skeleton"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

mkdir -p "$FASTAPI/app/core"
mkdir -p "$FASTAPI/app/services"
mkdir -p "$FASTAPI/app/routers"

# Python package markers
touch "$FASTAPI/app/__init__.py"
touch "$FASTAPI/app/core/__init__.py"
touch "$FASTAPI/app/services/__init__.py"
touch "$FASTAPI/app/routers/__init__.py"

echo "✅ Directory structure created:"
find "$FASTAPI/app" -type f | sort

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 2 — Copy new package files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cp "$OUTPUTS/security_unified.py"   "$FASTAPI/app/core/security.py"
cp "$OUTPUTS/invoice_service.py"    "$FASTAPI/app/services/invoice_service.py"
cp "$OUTPUTS/telegram_service.py"   "$FASTAPI/app/services/telegram_service.py"
cp "$OUTPUTS/invoices_router.py"    "$FASTAPI/app/routers/invoices.py"

echo "✅ New package files in place"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 3 — Replace root-level files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Back up originals before replacing
cp "$FASTAPI/telegram_handlers.py"  "$FASTAPI/telegram_handlers.py.bak"
cp "$FASTAPI/telegram_utils.py"     "$FASTAPI/telegram_utils.py.bak"
cp "$FASTAPI/main.py"               "$FASTAPI/main.py.bak"

cp "$OUTPUTS/telegram_handlers.py"  "$FASTAPI/telegram_handlers.py"
cp "$OUTPUTS/telegram_utils.py"     "$FASTAPI/telegram_utils.py"     # shim
cp "$OUTPUTS/main.py"               "$FASTAPI/main.py"

echo "✅ Root-level files replaced (.bak copies kept)"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 4 — Replace router files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cp "$FASTAPI/routers/auth_router.py"   "$FASTAPI/routers/auth_router.py.bak"
cp "$FASTAPI/routers/products_v2.py"   "$FASTAPI/routers/products_v2.py.bak"

cp "$OUTPUTS/auth_router.py"   "$FASTAPI/routers/auth_router.py"
cp "$OUTPUTS/products_v2.py"   "$FASTAPI/routers/products_v2.py"

echo "✅ Router files replaced (.bak copies kept)"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 5 — Copy frontend files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

WEBUI=./web_ui/src

mkdir -p "$WEBUI/api"
mkdir -p "$WEBUI/hooks"
mkdir -p "$WEBUI/components/InvoiceModule"
mkdir -p "$WEBUI/components/NotificationCenter"

cp "$OUTPUTS/invoiceApi.js"          "$WEBUI/api/invoiceApi.js"
cp "$OUTPUTS/useInvoiceActions.js"   "$WEBUI/hooks/useInvoiceActions.js"

# Back up and replace components
cp "$WEBUI/InvoiceModule.jsx"        "$WEBUI/InvoiceModule.jsx.bak"        2>/dev/null || true
cp "$WEBUI/NotificationCenter.jsx"   "$WEBUI/NotificationCenter.jsx.bak"   2>/dev/null || true

cp "$OUTPUTS/InvoiceModule.jsx"      "$WEBUI/components/InvoiceModule/InvoiceModule.jsx"
cp "$OUTPUTS/NotificationCenter.jsx" "$WEBUI/components/NotificationCenter/NotificationCenter.jsx"

# Copy CSS files into component folders (they are unchanged)
cp "$WEBUI/InvoiceModule.css"        "$WEBUI/components/InvoiceModule/InvoiceModule.css"      2>/dev/null || true
cp "$WEBUI/NotificationCenter.css"   "$WEBUI/components/NotificationCenter/NotificationCenter.css" 2>/dev/null || true

echo "✅ Frontend files in place"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Done — next steps"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "DEVELOPMENT:"
echo "  docker compose restart fastapi"
echo "  docker compose logs -f fastapi"
echo ""
echo "PRODUCTION:"
echo "  docker compose -f docker-compose.prod.yml build --no-cache fastapi"
echo "  docker compose -f docker-compose.prod.yml up -d fastapi"
echo ""
echo "Verify the API is healthy:"
echo "  curl http://localhost:8000/health"
echo "  curl http://localhost:8000/docs"
