@echo off
REM GameBot Live Server Startup Script

echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║              🎮 GAMEBOT MULTIPLAYER SERVER 🎮                  ║
echo ║            Live Server - Ready for Production                  ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Python is not installed or not in PATH
    echo Please install Python 3.11+ from https://www.python.org
    pause
    exit /b 1
)

echo ✓ Python found

REM Check if requirements installed
python -c "import importlib.util, sys; mods=['flask','flask_cors','flask_sqlalchemy','jwt','dotenv','redis']; missing=[m for m in mods if importlib.util.find_spec(m) is None]; sys.exit(1 if missing else 0)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo 📦 Installing dependencies...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ Failed to install dependencies
        pause
        exit /b 1
    )
    echo ✓ Dependencies installed
)

echo.
echo 🚀 Starting GameBot server...
echo.
echo ═══════════════════════════════════════════════════════════════════
echo.
echo   🎮 Server running at: http://localhost:5000
echo.
echo   📖 Open this URL in your browser to play!
echo.
echo   ✓ Login page will load automatically
echo   ✓ Create account or login to start
echo   ✓ Press Ctrl+C to stop server
echo.
echo ═══════════════════════════════════════════════════════════════════
echo.

python gamebot_multiplayer_server.py

pause
