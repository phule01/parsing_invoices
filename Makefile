# Makefile for Invoice Management System

.PHONY: help up down logs restart build clean ngrok ngrok-setup

help:
	@echo "═══════════════════════════════════════════════════════════════"
	@echo "Invoice Management System - Available Commands"
	@echo "═══════════════════════════════════════════════════════════════"
	@echo ""
	@echo "Basic Commands:"
	@echo "  make up              - Start all Docker containers"
	@echo "  make down            - Stop all Docker containers"
	@echo "  make build           - Build all Docker images"
	@echo "  make restart         - Restart all containers"
	@echo "  make clean           - Remove containers, volumes, and networks"
	@echo "  make logs            - Show logs from all containers"
	@echo ""
	@echo "Development & Testing:"
	@echo "  make ngrok           - Start ngrok tunnel (requires separate terminal)"
	@echo "  make ngrok-setup     - Install ngrok (macOS/Linux)"
	@echo "  make run-ngrok       - Full app + ngrok (all-in-one, Linux/macOS only)"
	@echo ""
	@echo "Service URLs:"
	@echo "  Web UI:    http://localhost:3000"
	@echo "  API:       http://localhost:8000"
	@echo "  API Docs:  http://localhost:8000/docs"
	@echo "  Database:  localhost:5432"
	@echo "═══════════════════════════════════════════════════════════════"

# ─────────────────────────────────────────────────────────────────────────────
# Docker Management
# ─────────────────────────────────────────────────────────────────────────────

up:
	@echo "🚀 Starting Docker containers..."
	docker-compose up -d --build
	@echo "✅ Containers started!"
	@echo ""
	@echo "Services:"
	@echo "  • Web UI:    http://localhost:3000"
	@echo "  • API:       http://localhost:8000"
	@echo "  • Database:  localhost:5432"

down:
	@echo "⏹️  Stopping Docker containers..."
	docker-compose down

restart:
	@echo "🔄 Restarting containers..."
	docker-compose restart
	@echo "✅ Containers restarted!"

build:
	@echo "🏗️  Building Docker images..."
	docker-compose build --no-cache

logs:
	docker-compose logs -f

logs-api:
	docker-compose logs -f tool_orc_fastapi

logs-web:
	docker-compose logs -f tool_orc_web

logs-email:
	docker-compose logs -f tool_orc_email_listener

logs-db:
	docker-compose logs -f tool_orc_postgres

clean:
	@echo "🧹 Cleaning up Docker resources..."
	docker-compose down -v
	docker system prune -f
	@echo "✅ Cleaned!"

# ─────────────────────────────────────────────────────────────────────────────
# Ngrok Integration
# ─────────────────────────────────────────────────────────────────────────────

ngrok-setup:
	@echo "📥 Installing ngrok..."
	@if command -v brew >/dev/null; then \
		brew install ngrok; \
	elif command -v apt-get >/dev/null; then \
		sudo apt-get update && sudo apt-get install -y ngrok; \
	else \
		echo "Please install ngrok manually from: https://ngrok.com/download"; \
		exit 1; \
	fi
	@echo "✅ Ngrok installed!"
	@echo ""
	@echo "Next: Configure your authtoken"
	@echo "  ngrok config add-authtoken YOUR_TOKEN"

ngrok:
	@echo "🌐 Starting ngrok tunnel..."
	@echo "   This requires TELEGRAM_WEBHOOK_URL to be set manually in .env"
	@echo ""
	ngrok http 8000
	@echo ""
	@echo "⚠️  After ngrok starts:"
	@echo "  1. Copy the https:// URL"
	@echo "  2. Update .env:"
	@echo "     TELEGRAM_WEBHOOK_URL=https://YOUR_URL/api/telegram/webhook"
	@echo "  3. Restart FastAPI:"
	@echo "     docker-compose restart tool_orc_fastapi"

run-ngrok: up
	@echo ""
	@echo "🚀 Full App + Ngrok Setup"
	@echo "  This will:"
	@echo "  • Start Docker containers"
	@echo "  • Launch ngrok tunnel"
	@echo "  • Update Telegram webhook URL"
	@echo "  • Restart FastAPI"
	@echo ""
	@chmod +x ./run-with-ngrok.sh
	./run-with-ngrok.sh

# ─────────────────────────────────────────────────────────────────────────────
# Database & Testing
# ─────────────────────────────────────────────────────────────────────────────

db-shell:
	@echo "🔗 Connecting to PostgreSQL..."
	docker-compose exec tool_orc_postgres psql -U postgres -d tool_orc_db

db-backup:
	@echo "💾 Backing up database..."
	docker-compose exec tool_orc_postgres pg_dump -U postgres tool_orc_db > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "✅ Backup created!"

# ─────────────────────────────────────────────────────────────────────────────
# Status & Info
# ─────────────────────────────────────────────────────────────────────────────

status:
	@docker-compose ps

health:
	@echo "🏥 Checking service health..."
	@echo ""
	@echo "FastAPI Health:"
	@curl -s http://localhost:8000/health | jq . || echo "❌ Not responding"
	@echo ""
	@echo "Telegram Status:"
	@curl -s http://localhost:8000/api/telegram/status | jq . || echo "❌ Not responding"
	@echo ""
	@echo "Database Connection:"
	@docker-compose exec -T tool_orc_postgres pg_isready || echo "❌ Not responding"
