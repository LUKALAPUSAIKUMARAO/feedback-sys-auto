# ============================================================
# Bilvantis TIP — Start All Services (No Docker)
# Opens separate PowerShell windows for each service
# ============================================================

$ROOT = Split-Path $PSScriptRoot -Parent

Write-Host ""
Write-Host "=== Bilvantis TIP — Starting Services ===" -ForegroundColor Cyan
Write-Host ""

function Start-Service($name, $color, $scriptBlock) {
    $cmd = "& { Set-Location '$ROOT'; $scriptBlock }"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd -WindowStyle Normal
    Write-Host "  Started: $name" -ForegroundColor $color
}

# Backend API
Start-Service "FastAPI Backend (port 8000)" "Green" @"
    Set-Location '$ROOT\backend'
    if (Test-Path '.venv\Scripts\Activate.ps1') { & .\.venv\Scripts\Activate.ps1 }
    `$host.UI.RawUI.WindowTitle = 'TIP — FastAPI Backend'
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"@

Start-Sleep 2

# Celery Worker
Start-Service "Celery Worker" "Yellow" @"
    Set-Location '$ROOT\backend'
    if (Test-Path '.venv\Scripts\Activate.ps1') { & .\.venv\Scripts\Activate.ps1 }
    `$host.UI.RawUI.WindowTitle = 'TIP — Celery Worker'
    python -m celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2 -P threads
"@

Start-Sleep 1

# Celery Beat (cron scheduler)
Start-Service "Celery Beat (Scheduler)" "Magenta" @"
    Set-Location '$ROOT\backend'
    if (Test-Path '.venv\Scripts\Activate.ps1') { & .\.venv\Scripts\Activate.ps1 }
    `$host.UI.RawUI.WindowTitle = 'TIP — Celery Beat'
    python -m celery -A app.tasks.celery_app beat --loglevel=info
"@

Start-Sleep 1

# Frontend
Start-Service "Next.js Frontend (port 3000)" "Cyan" @"
    Set-Location '$ROOT\frontend'
    `$host.UI.RawUI.WindowTitle = 'TIP — Next.js Frontend'
    npm run dev
"@

Write-Host ""
Write-Host "  All services started in separate windows." -ForegroundColor Cyan
Write-Host ""
Write-Host "  URLs:" -ForegroundColor White
Write-Host "    Frontend:  http://localhost:3000" -ForegroundColor Green
Write-Host "    API:       http://localhost:8000" -ForegroundColor Green
Write-Host "    API Docs:  http://localhost:8000/api/docs" -ForegroundColor Green
Write-Host ""
Write-Host "  Default Admin Credentials:" -ForegroundColor White
Write-Host "    Email:    admin@bilvantis.io" -ForegroundColor Yellow
Write-Host "    Password: Admin@1234" -ForegroundColor Yellow
Write-Host ""
