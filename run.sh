#!/bin/bash
# run.sh — Start the Tool ORC Invoice System using Docker Compose v2
# Usage: ./run.sh [--build] [--prod]
#
#   --build   Force rebuild of all images before starting
#   --prod    Use docker-compose.prod.yml (production config)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Parse args ────────────────────────────────────────────────────────────────
BUILD_FLAG=""
COMPOSE_FILE="docker-compose.yml"

for arg in "$@"; do
  case $arg in
    --build) BUILD_FLAG="--build" ;;
    --prod)  COMPOSE_FILE="docker-compose.prod.yml" ;;
  esac
done

# ── Verify Docker Compose v2 ──────────────────────────────────────────────────
if ! docker compose version &>/dev/null; then
  echo "❌ Docker Compose v2 not found."
  echo "   Install Docker Desktop ≥ 4.x or Docker Engine + Compose plugin."
  echo "   See: https://docs.docker.com/compose/install/"
  exit 1
fi

COMPOSE_VER=$(docker compose version --short 2>/dev/null || echo "unknown")
echo "🐳 Docker Compose v2 (version: $COMPOSE_VER)"

# ── Check .env ────────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  echo "⚠️  .env not found — copying from .env-example"
  cp .env-example .env
  echo "✏️  Edit .env with your credentials, then re-run this script."
  exit 1
fi

echo ""
echo "🚀 Starting Tool ORC Invoice System..."
echo "   Config: $COMPOSE_FILE"
echo ""

# ── Database volume check ─────────────────────────────────────────────────────
if docker volume ls --quiet 2>/dev/null | grep -q "postgres_data"; then
  echo "✅ Existing database volume found — data preserved"
else
  echo "📦 First run — new database volume will be created"
fi
echo ""

# ── Start containers ──────────────────────────────────────────────────────────
echo "🏗️  Starting containers..."
docker compose -f "$COMPOSE_FILE" up -d $BUILD_FLAG

echo ""
echo "⏳ Waiting for services..."

# ── Wait: PostgreSQL ──────────────────────────────────────────────────────────
echo "  ⏳ PostgreSQL..."
for i in $(seq 1 90); do
  HEALTH=$(docker inspect --format='{{.State.Health.Status}}' tool_orc_postgres 2>/dev/null || echo "not_found")
  if [[ "$HEALTH" == "healthy" ]]; then
    echo "  ✅ PostgreSQL ready"
    break
  fi
  if [[ $i -eq 90 ]]; then
    echo "  ⚠️  PostgreSQL health check timed out"
  fi
  sleep 1
done

# ── Wait: FastAPI ──────────────────────────────────────────────────────────────
echo "  ⏳ FastAPI..."
for i in $(seq 1 60); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    echo "  ✅ FastAPI ready"
    break
  fi
  if [[ $i -eq 60 ]]; then
    echo "  ⚠️  FastAPI taking longer than expected"
    echo "     Check logs: docker compose logs fastapi"
  fi
  sleep 1
done

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "✅ System started!"
echo ""
echo "📊 Container Status:"
docker compose -f "$COMPOSE_FILE" ps

echo ""
echo "🌐 Access Points:"
echo "  • Web UI:   http://localhost:3000"
echo "  • API Docs: http://localhost:8000/docs"
echo "  • API:      http://localhost:8000"
echo ""
echo "📖 Useful Commands (Docker Compose v2):"
echo "  docker compose stop                    # Stop (keeps data)"
echo "  docker compose start                   # Resume"
echo "  docker compose logs -f                 # Live logs"
echo "  docker compose logs -f fastapi         # FastAPI only"
echo "  docker compose logs -f email_listener  # Email listener"
echo "  docker compose ps                      # Status"
echo "  docker compose build --no-cache        # Rebuild"
echo "  docker compose up -d --force-recreate  # Restart latest"
echo ""
echo "⚠️  WARNING: Never run 'docker compose down -v' — deletes database!"
echo "═══════════════════════════════════════════════════════════"
echo ""

# ── Ngrok (optional) ──────────────────────────────────────────────────────────
if command -v ngrok &>/dev/null && ! pgrep -x "ngrok" &>/dev/null; then
  echo "🌍 Starting ngrok tunnel (for Telegram webhook)..."
  ngrok http 8000 --log=stdout >/dev/null 2>&1 &
  sleep 3
  NGROK_URL=$(curl -sf http://localhost:4040/api/tunnels 2>/dev/null \
    | grep -o '"public_url":"[^"]*' | grep https | cut -d'"' -f4 | head -1 || echo "")
  if [[ -n "$NGROK_URL" ]]; then
    echo "✅ ngrok: $NGROK_URL"
    sed -i.bak "s|TELEGRAM_WEBHOOK_URL=.*|TELEGRAM_WEBHOOK_URL=$NGROK_URL/api/telegram/webhook|" .env
    docker compose -f "$COMPOSE_FILE" restart fastapi >/dev/null 2>&1
    echo "✅ Telegram webhook: $NGROK_URL/api/telegram/webhook"
  else
    echo "ℹ️  ngrok started (could not read URL — check http://localhost:4040)"
  fi
elif pgrep -x "ngrok" &>/dev/null; then
  echo "ℹ️  ngrok already running"
fi

# ── Open browser ──────────────────────────────────────────────────────────────
sleep 1
if [[ "${OSTYPE:-}" == darwin* ]]; then
  open "http://localhost:3000" 2>/dev/null || true
elif command -v xdg-open &>/dev/null; then
  xdg-open "http://localhost:3000" 2>/dev/null || true
fi
