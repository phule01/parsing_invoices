#!/bin/bash

echo "🚀 Starting Tool ORC Invoice System..."
echo ""

# Check if database volume exists
DB_VOLUME=$(docker volume ls | grep postgres_data)
if [ -z "$DB_VOLUME" ]; then
    echo "📦 Creating new database volume (first run)..."
else
    echo "✅ Existing database found - data will be preserved"
fi

echo ""
echo "🐳 Building and starting Docker containers..."
# Don't rebuild unless absolutely needed to preserve data integrity
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be healthy..."

# Wait for PostgreSQL to be healthy
echo "  ⏳ PostgreSQL..."
POSTGRES_READY=0
for i in {1..30}; do
    if docker-compose exec -T tool_orc_postgres pg_isready -U postgres > /dev/null 2>&1; then
        echo "  ✅ PostgreSQL ready"
        POSTGRES_READY=1
        break
    fi
    sleep 1
done

if [ $POSTGRES_READY -eq 0 ]; then
    echo "  ❌ PostgreSQL failed to start"
fi

# Wait for FastAPI to be healthy
echo "  ⏳ FastAPI..."
FASTAPI_READY=0
for i in {1..60}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "  ✅ FastAPI ready"
        FASTAPI_READY=1
        break
    fi
    sleep 1
done

if [ $FASTAPI_READY -eq 0 ]; then
    echo "  ⚠️  FastAPI taking longer to start (this is normal)"
fi

echo ""
echo "✅ Services started!"
echo ""

# Check container status
echo "📊 Service Status:"
docker-compose ps

echo ""
echo "🌐 Access Points:"
echo "  • Web UI: http://localhost:3000"
echo "  • API Docs: http://localhost:8000/docs"
echo "  • PostgreSQL: localhost:5432"
echo ""

# Start ngrok if not already running
if ! pgrep -x "ngrok" > /dev/null; then
    echo "🌍 Starting ngrok tunnel (optional for Telegram webhook)..."
    echo "   This will create a public URL for your local server"
    ngrok http 8000 --log=stdout > /dev/null 2>&1 &
    sleep 2
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | grep -o '"public_url":"[^"]*' | cut -d'"' -f4 | head -1)
    if [ ! -z "$NGROK_URL" ]; then
        echo "✅ ngrok running! Public URL: $NGROK_URL"
        # Update .env with webhook URL
        sed -i.bak "s|TELEGRAM_WEBHOOK_URL=.*|TELEGRAM_WEBHOOK_URL=$NGROK_URL/api/telegram/webhook|" .env
        docker-compose restart tool_orc_fastapi > /dev/null 2>&1
        echo "✅ Telegram webhook updated and FastAPI restarted"
    else
        echo "ℹ️  ngrok started in background"
    fi
else
    echo "ℹ️  ngrok already running"
fi

echo ""
echo "📖 Useful Commands:"
echo "  docker-compose stop       # Stop (keeps data)"
echo "  docker-compose start      # Resume"
echo "  docker builder prune -af  # Clear build cache only"
echo "  docker-compose build --no-cache          # Rebuild images"
echo "  docker-compose up -d --force-recreate    # Restart with new images"
echo "  docker-compose logs -f    # View live logs"
echo "  docker-compose ps         # Check status"
echo ""
echo "⚠️  WARNING: Never use 'docker-compose down -v' (deletes database!)"
echo ""
