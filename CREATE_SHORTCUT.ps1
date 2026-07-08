#!/usr/bin/env pwsh
# Create GameBot Desktop Shortcut

Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Creating GameBot Desktop Shortcut...            ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

try {
    $shell = New-Object -com "WScript.Shell"
    $desktopPath = "$env:USERPROFILE\Desktop"
    $lnkPath = "$desktopPath\GameBot.lnk"
    $targetPath = "c:\Users\ytc-y\code projects\launcher.py"
    $workingDir = "c:\Users\ytc-y\code projects"
    
    Write-Host "Creating shortcut..."
    $lnk = $shell.CreateShortcut($lnkPath)
    $lnk.TargetPath = "python"
    $lnk.Arguments = "`"$targetPath`""
    $lnk.WorkingDirectory = $workingDir
    $lnk.Description = "GameBot - Multiplayer Gaming Platform"
    $lnk.IconLocation = "python.exe"
    $lnk.Save()
    
    Write-Host "✅ Shortcut created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📍 Location: $lnkPath" -ForegroundColor Green
    Write-Host ""
    Write-Host "Now you can:" -ForegroundColor Yellow
    Write-Host "  • Double-click 'GameBot' on your desktop to launch" -ForegroundColor Yellow
    Write-Host "  • Right-click → Pin to Start for quick access" -ForegroundColor Yellow
    Write-Host "  • Right-click → Pin to Taskbar for taskbar access" -ForegroundColor Yellow
    Write-Host ""
    
} catch {
    Write-Host "❌ Error creating shortcut: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Manual alternative:" -ForegroundColor Yellow
    Write-Host "  1. Right-click desktop" -ForegroundColor Yellow
    Write-Host "  2. New → Shortcut" -ForegroundColor Yellow
    Write-Host "  3. Enter: python `"c:\Users\ytc-y\code projects\launcher.py`"" -ForegroundColor Yellow
    Write-Host "  4. Name it: GameBot" -ForegroundColor Yellow
    Write-Host "  5. Click Finish" -ForegroundColor Yellow
}

Read-Host "Press Enter to exit"
