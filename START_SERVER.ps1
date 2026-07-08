#!/usr/bin/env pwsh
# GameBot Live Server Startup Script (PowerShell)

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║              🎮 GAMEBOT MULTIPLAYER SERVER 🎮                  ║" -ForegroundColor Cyan
Write-Host "║            Live Server - Ready for Production                  ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Error: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.11+ from https://www.python.org" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if requirements installed
$missingModules = python -c "import importlib.util; mods=['flask','flask_cors','flask_sqlalchemy','jwt','dotenv','redis']; print(','.join(m for m in mods if importlib.util.find_spec(m) is None))" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to check Python dependencies" -ForegroundColor Red
    Write-Host $missingModules -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

if ($missingModules) {
    Write-Host ""
    Write-Host "📦 Installing dependencies..." -ForegroundColor Yellow
    python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to install dependencies" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "✓ Dependencies installed" -ForegroundColor Green
}

Write-Host ""
Write-Host "🚀 Starting GameBot server..." -ForegroundColor Yellow
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "   🎮 Server running at: http://localhost:5000" -ForegroundColor Green
Write-Host ""
Write-Host "   📖 Open this URL in your browser to play!" -ForegroundColor Green
Write-Host ""
Write-Host "   ✓ Login page will load automatically" -ForegroundColor Green
Write-Host "   ✓ Create account or login to start" -ForegroundColor Green
Write-Host "   ✓ Press Ctrl+C to stop server" -ForegroundColor Green
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

python gamebot_multiplayer_server.py

Read-Host "Press Enter to exit"
