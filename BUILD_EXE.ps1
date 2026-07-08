#!/usr/bin/env pwsh
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "Building GameBot.exe..." -ForegroundColor Cyan

try {
    python --version | Out-Host
} catch {
    Write-Host "Python is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing PyInstaller..." -ForegroundColor Yellow
    python -m pip install pyinstaller
}

$dataFiles = @(
    "gamebot_multiplayer_server.py;.",
    "master.html;.",
    "login.html;.",
    "dashboard.html;.",
    "requirements.txt;.",
    ".env.example;."
)

$hiddenImports = @(
    "bcrypt",
    "cryptography",
    "cryptography.fernet",
    "dotenv",
    "flask",
    "flask_cors",
    "flask_sqlalchemy",
    "jwt",
    "redis",
    "sqlalchemy"
)

$args = @(
    "--clean",
    "--noconsole",
    "--onefile",
    "--name", "GameBot"
)

foreach ($item in $dataFiles) {
    $args += "--add-data"
    $args += $item
}

foreach ($item in $hiddenImports) {
    $args += "--hidden-import"
    $args += $item
}

$args += "launcher.py"

python -m PyInstaller @args

Write-Host ""
Write-Host "Done: dist\GameBot.exe" -ForegroundColor Green
Write-Host "Upload dist\GameBot.exe to a GitHub Release." -ForegroundColor Green
