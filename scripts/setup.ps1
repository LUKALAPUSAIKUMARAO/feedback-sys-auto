# ============================================================
# Bilvantis Training Intelligence Platform — Setup Script
# Replaces Docker Compose — runs services directly on Windows
# ============================================================
param(
    [switch]$SkipPython,
    [switch]$SkipNode,
    [switch]$SkipDB
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path $PSScriptRoot -Parent

Write-Host ""
Write-Host "=== Bilvantis TIP — Setup ===" -ForegroundColor Cyan
Write-Host ""

# ── Python venv ───────────────────────────────────────────────────────────────
if (-not $SkipPython) {
    Write-Host "[1/4] Setting up Python virtual environment..." -ForegroundColor Yellow
    Push-Location "$ROOT\backend"

    if (-not (Test-Path ".venv")) {
        python -m venv .venv
    }

    & .\.venv\Scripts\Activate.ps1
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
    Write-Host "      Python dependencies installed." -ForegroundColor Green

    if (-not (Test-Path ".env")) {
        Copy-Item ".env.example" ".env"
        Write-Host "      .env created from .env.example — EDIT IT before starting." -ForegroundColor Magenta
    }

    Pop-Location
}

# ── Node.js ───────────────────────────────────────────────────────────────────
if (-not $SkipNode) {
    Write-Host "[2/4] Installing Node.js dependencies..." -ForegroundColor Yellow
    Push-Location "$ROOT\frontend"
    npm install --legacy-peer-deps
    Write-Host "      Node dependencies installed." -ForegroundColor Green
    Pop-Location
}

# ── PostgreSQL Check ──────────────────────────────────────────────────────────
if (-not $SkipDB) {
    Write-Host "[3/4] Checking PostgreSQL & pgvector..." -ForegroundColor Yellow
    $pgRunning = $false
    try {
        $result = & psql --version 2>&1
        Write-Host "      PostgreSQL: $result" -ForegroundColor Green
        $pgRunning = $true
    } catch {
        Write-Host "      WARNING: psql not found. Install PostgreSQL 15+ with pgvector." -ForegroundColor Red
        Write-Host "      Download: https://www.postgresql.org/download/" -ForegroundColor Red
    }

    if ($pgRunning) {
        Write-Host "      Running database migrations..." -ForegroundColor Yellow
        $env_content = Get-Content "$ROOT\backend\.env" | Where-Object { $_ -match "^SYNC_DATABASE_URL" }
        if ($env_content) {
            $db_url = ($env_content -split "=", 2)[1].Trim()
            # Extract connection parts for psql
            Write-Host "      DB URL detected. Run manually if needed:" -ForegroundColor Cyan
            Write-Host "      psql `$DB_URL -f backend/migrations/001_init.sql" -ForegroundColor White
        }
    }
}

# ── Redis Check ───────────────────────────────────────────────────────────────
Write-Host "[4/4] Checking Redis..." -ForegroundColor Yellow
try {
    $redisCli = Get-Command redis-cli -ErrorAction SilentlyContinue
    if ($redisCli) {
        $ping = & redis-cli ping 2>&1
        if ($ping -eq "PONG") {
            Write-Host "      Redis is running." -ForegroundColor Green
        } else {
            Write-Host "      Redis not responding. Start it with: redis-server" -ForegroundColor Red
        }
    } else {
        Write-Host "      redis-cli not found. Install Redis for Windows:" -ForegroundColor Red
        Write-Host "      https://github.com/microsoftarchive/redis/releases" -ForegroundColor Red
        Write-Host "      OR use: winget install Redis.Redis" -ForegroundColor Yellow
    }
} catch {
    Write-Host "      Redis check skipped." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Setup complete. Run: .\scripts\start.ps1 ===" -ForegroundColor Cyan
Write-Host ""
