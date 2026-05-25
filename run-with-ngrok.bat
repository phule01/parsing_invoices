@echo off
REM ############################################################################
REM Tool ORC Invoice System - Startup Script for Windows
REM ############################################################################

setlocal enabledelayedexpansion

echo.
echo 🚀 Starting Tool ORC Invoice System...
echo.

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running.
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)

REM Check if database volume exists
echo Checking database volume...
docker volume ls 2>nul | find "postgres_data" >nul
if errorlevel 1 (
    echo 📦 Creating new database volume (first run)...
) else (
    echo ✅ Existing database found - data will be preserved
)

echo.
echo 🐳 Starting Docker containers...
docker-compose up -d

echo.
echo ⏳ Waiting for services to be healthy...

REM Wait for PostgreSQL
echo   ⏳ PostgreSQL...
set POSTGRES_READY=0
for /L %%i in (1,1,30) do (
    docker-compose exec -T tool_orc_postgres pg_isready -U postgres >nul 2>&1
    if errorlevel 0 (
        echo   ✅ PostgreSQL ready
        set POSTGRES_READY=1
        goto postgres_done
    )
    timeout /t 1 /nobreak >nul
)
:postgres_done
if %POSTGRES_READY% equ 0 (
    echo   ❌ PostgreSQL failed to start
)

REM Wait for FastAPI
echo   ⏳ FastAPI...
set FASTAPI_READY=0
for /L %%i in (1,1,60) do (
    curl -s http://localhost:8000/health >nul 2>&1
    if errorlevel 0 (
        echo   ✅ FastAPI ready
        set FASTAPI_READY=1
        goto fastapi_done
    )
    timeout /t 1 /nobreak >nul
)
:fastapi_done
if %FASTAPI_READY% equ 0 (
    echo   ⚠️  FastAPI taking longer to start (this is normal)
)

echo.
echo ✅ Services started!
echo.

REM Check container status
echo 📊 Service Status:
docker-compose ps

echo.
echo 🌐 Access Points:
echo   • Web UI: http://localhost:3000
echo   • API Docs: http://localhost:8000/docs
echo   • PostgreSQL: localhost:5432
echo.

REM Check if ngrok is available
where ngrok >nul 2>&1
if errorlevel 1 (
    echo ℹ️  ngrok not installed (optional)
    echo    Install from: https://ngrok.com/download
) else (
    REM Check if ngrok is already running
    tasklist /FI "IMAGENAME eq ngrok.exe" 2>nul | find /I /N "ngrok.exe">nul
    if errorlevel 1 (
        echo 🌍 Starting ngrok tunnel (optional for Telegram webhook)...
        start "" ngrok http 8000
        timeout /t 2 /nobreak >nul
        echo ✅ ngrok launched
    ) else (
        echo ℹ️  ngrok already running
    )
)

echo.
echo 📖 Useful Commands:
echo   docker-compose stop       # Stop (keeps data)
echo   docker-compose start      # Resume
echo   docker-compose logs -f    # View live logs
echo   docker-compose ps         # Check status
echo.
echo ⚠️  WARNING: Never use 'docker-compose down -v' (deletes database!)
echo.

pause
