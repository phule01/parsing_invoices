#!/bin/bash
# README - Quick Reference

cd "$(dirname "$0")" 2>/dev/null || cd "$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║     Invoice Management System - Quick Command Reference          ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo ""

if [ -f "run-with-ngrok.sh" ]; then
    echo "✨ QUICKEST START (with Telegram support):"
    echo "   ./run-with-ngrok.sh"
    echo ""
fi

if command -v make &> /dev/null; then
    echo "📋 USING MAKE:"
    echo "   make help           # Show all commands"
    echo "   make run-ngrok      # Run with Telegram support"
    echo "   make up             # Just start containers"
    echo ""
fi

echo "🐳 DOCKER COMMANDS:"
echo "   docker-compose up -d --build     # Start containers"
echo "   docker-compose down              # Stop containers"
echo "   docker-compose logs -f           # View logs"
echo "   docker-compose ps                # Check status"
echo ""

echo "🌐 SERVICE URLS:"
echo "   Web UI:   http://localhost:3000"
echo "   API:      http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo "   Database: localhost:5432"
echo ""

echo "📖 DOCUMENTATION:"
echo "   QUICKSTART_NGROK.md  - Simple 30-second setup"
echo "   NGROK_SETUP.md       - Complete guide with troubleshooting"
echo "   Makefile             - All available make commands"
echo ""

echo "╚═══════════════════════════════════════════════════════════════════╝"
echo ""
