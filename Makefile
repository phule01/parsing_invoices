# Makefile for Tool ORC Invoice Management System
# Requires: Docker Compose v2  (docker compose, NOT docker-compose)

.PHONY: help up up-prod down stop start restart build build-no-cache \
        logs logs-api logs-web logs-email logs-db \
        clean clean-images status health \
        db-shell db-backup \
        ngrok ngrok-setup

# ─────────────────────────────────────────────────────────────────────────────
# Help
# ─────────────────────────────────────────────────────────────────────────────

help:
	@echo "═══════════════════════════════════════════════════════════════════"
	@echo "  Tool ORC Invoice Management System — Make Commands"
	@echo "═══════════════════════════════════════════════════════════════════"
	@echo ""
	@echo "  Start / Stop:"
	@echo "    make up              Start all containers (dev)"
	@echo "    make up-prod         Start all containers (production)"
	@echo "    make down            Stop and remove containers (keeps data)"
	@echo "    make stop            Stop containers (keeps data)"
	@echo "    make start           Resume stopped containers"
	@echo "    make restart         Restart all containers"
	@echo ""
	@echo "  Build:"
	@echo "    make build           Build images (cached)"
	@echo "    make build-no-cache  Rebuild images from scratch"
	@echo ""
	@echo "  Logs:"
	@echo "    make logs            Stream all logs"
	@echo "    make logs-api        Stream FastAPI logs"
	@echo "    make logs-web        Stream Web UI logs"
	@echo "    make logs-email      Stream email listener logs"
	@echo "    make logs-db         Stream PostgreSQL logs"
	@echo ""
	@echo "  Status & Health:"
	@echo "    make status          Show container status"
	@echo "    make health          Check service health endpoints"
	@echo ""
	@echo "  Database:"
	@echo "    make db-shell        Open psql shell"
	@echo "    make db-backup       Dump database to SQL file"
	@echo ""
	@echo "  Cleanup:"
	@echo "    make clean           Remove containers + volumes (⚠ deletes DB!)"
	@echo "    make clean-images    Remove built images (keeps data)"
	@echo ""
	@echo "  Ngrok (Telegram webhook):"
	@echo "    make ngrok           Start ngrok tunnel on port 8000"
	@echo "    make ngrok-setup     Install ngrok"
	@echo ""
	@echo "  Service URLs:"
	@echo "    Web UI:    http://localhost:3000"
	@echo "    API:       http://localhost:8000"
	@echo "    API Docs:  http://localhost:8000/docs"
	@echo "    Database:  localhost:5432"
	@echo "═══════════════════════════════════════════════════════════════════"

# ─────────────────────────────────────────────────────────────────────────────
# Start / Stop
# ─────────────────────────────────────────────────────────────────────────────

up:
	@echo "🚀 Starting containers (dev)..."
	docker compose up -d --build
	@echo "✅ Done! Web UI: http://localhost:3000"

up-prod:
	@echo "🚀 Starting containers (production)..."
	docker compose -f docker-compose.prod.yml up -d --build
	@echo "✅ Done! Web UI: http://localhost:3000"

down:
	@echo "⏹️  Stopping and removing containers..."
	docker compose down
	@echo "✅ Containers removed (data preserved in volumes)"

stop:
	@echo "⏸️  Stopping containers..."
	docker compose stop

start:
	@echo "▶️  Resuming containers..."
	docker compose start

restart:
	@echo "🔄 Restarting all containers..."
	docker compose restart
	@echo "✅ Restarted!"

# ─────────────────────────────────────────────────────────────────────────────
# Build
# ─────────────────────────────────────────────────────────────────────────────

build:
	@echo "🏗️  Building images..."
	docker compose build

build-no-cache:
	@echo "🏗️  Rebuilding images (no cache)..."
	docker compose build --no-cache

# ─────────────────────────────────────────────────────────────────────────────
# Logs  (use service names, not container names)
# ─────────────────────────────────────────────────────────────────────────────

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f fastapi

logs-web:
	docker compose logs -f web

logs-email:
	docker compose logs -f email_listener

logs-db:
	docker compose logs -f postgres

# ─────────────────────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────────────────────

clean:
	@echo "⚠️  WARNING: This will DELETE all containers AND the database volume!"
	@echo "   Aborting in 5 seconds — press Ctrl-C to cancel..."
	@sleep 5
	docker compose down -v
	docker system prune -f
	@echo "✅ Cleaned!"

clean-images:
	@echo "🧹 Removing built images (data volumes preserved)..."
	docker compose down --rmi local
	@echo "✅ Images removed. Run 'make build' to rebuild."

# ─────────────────────────────────────────────────────────────────────────────
# Ngrok (optional — needed for Telegram webhook on local machine)
# ─────────────────────────────────────────────────────────────────────────────

ngrok-setup:
	@echo "📥 Installing ngrok..."
	@if command -v brew >/dev/null 2>&1; then \
	    brew install ngrok; \
	elif command -v apt-get >/dev/null 2>&1; then \
	    curl -fsSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null; \
	    echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list; \
	    sudo apt-get update && sudo apt-get install -y ngrok; \
	else \
	    echo "Please install ngrok manually: https://ngrok.com/download"; \
	    exit 1; \
	fi
	@echo "✅ ngrok installed."
	@echo "   Next: ngrok config add-authtoken YOUR_TOKEN"

ngrok:
	@echo "🌐 Starting ngrok tunnel on port 8000..."
	@echo "   Copy the https:// URL, then:"
	@echo "   1. Update .env: TELEGRAM_WEBHOOK_URL=https://YOUR_URL/api/telegram/webhook"
	@echo "   2. Run: docker compose restart fastapi"
	@echo ""
	ngrok http 8000

# ─────────────────────────────────────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────────────────────────────────────

db-shell:
	@echo "🔗 Connecting to PostgreSQL..."
	docker compose exec postgres psql -U $${DB_USER:-postgres} -d $${DB_NAME:-tool_orc_db}

db-backup:
	@echo "💾 Backing up database..."
	docker compose exec -T postgres \
	    pg_dump -U $${DB_USER:-postgres} $${DB_NAME:-tool_orc_db} \
	    > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "✅ Backup saved."

# ─────────────────────────────────────────────────────────────────────────────
# Status & Health
# ─────────────────────────────────────────────────────────────────────────────

status:
	@docker compose ps

health:
	@echo "🏥 Checking service health..."
	@echo ""
	@echo "FastAPI Health:"
	@curl -sf http://localhost:8000/health | python3 -m json.tool 2>/dev/null || echo "❌ Not responding"
	@echo ""
	@echo "Telegram Status:"
	@curl -sf http://localhost:8000/api/telegram/status | python3 -m json.tool 2>/dev/null || echo "❌ Not responding"
	@echo ""
	@echo "Database:"
	@docker compose exec -T postgres pg_isready -U $${DB_USER:-postgres} || echo "❌ Not responding"
