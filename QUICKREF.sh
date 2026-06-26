#!/bin/bash
# QUICKREF.sh — Quick command reference for Tool ORC Invoice System

cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null || cd "$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║       Tool ORC Invoice System — Quick Command Reference             ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

echo "✨ QUICKEST START:"
echo "   ./run.sh                  # Start (dev, no rebuild)"
echo "   ./run.sh --build          # Start with forced image rebuild"
echo "   ./run.sh --prod           # Start in production mode"
echo ""

if command -v make &>/dev/null; then
  echo "📋 USING MAKE:"
  echo "   make help                # Show all commands"
  echo "   make up                  # Start (dev)"
  echo "   make up-prod             # Start (production)"
  echo "   make down                # Stop containers"
  echo "   make logs                # Live logs"
  echo "   make status              # Container status"
  echo ""
fi

echo "🐳 DOCKER COMPOSE v2 COMMANDS:"
echo "   docker compose up -d --build          # Start + rebuild"
echo "   docker compose down                   # Stop (keep data)"
echo "   docker compose logs -f                # Live logs"
echo "   docker compose logs -f fastapi        # FastAPI logs"
echo "   docker compose logs -f email_listener # Email listener logs"
echo "   docker compose ps                     # Check status"
echo "   docker compose build --no-cache       # Full rebuild"
echo "   docker compose restart fastapi        # Restart one service"
echo ""
echo "   # Production:"
echo "   docker compose -f docker-compose.prod.yml up -d --build"
echo ""

echo "🌐 SERVICE URLs:"
echo "   Web UI:    http://localhost:3000"
echo "   API:       http://localhost:8000"
echo "   API Docs:  http://localhost:8000/docs"
echo "   Database:  localhost:5432"
echo ""

echo "⚠️  DANGER:"
echo "   Never run 'docker compose down -v' — it DELETES the database!"
echo "   Use 'docker compose down' (no -v) to safely stop."
echo ""
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

