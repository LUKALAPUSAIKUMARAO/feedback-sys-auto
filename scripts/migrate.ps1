# Run database migrations
param([string]$DbUrl = "")

$ROOT = Split-Path $PSScriptRoot -Parent

if (-not $DbUrl) {
    $envFile = "$ROOT\backend\.env"
    if (Test-Path $envFile) {
        $line = Get-Content $envFile | Where-Object { $_ -match "^SYNC_DATABASE_URL" }
        if ($line) { $DbUrl = ($line -split "=", 2)[1].Trim() }
    }
}

if (-not $DbUrl) {
    Write-Host "ERROR: No database URL found. Set SYNC_DATABASE_URL in backend/.env" -ForegroundColor Red
    exit 1
}

Write-Host "Running migrations against: $($DbUrl -replace ':[^:@]+@', ':***@')" -ForegroundColor Cyan
psql $DbUrl -f "$ROOT\backend\migrations\001_init.sql"

if ($LASTEXITCODE -eq 0) {
    Write-Host "Migrations applied successfully." -ForegroundColor Green
} else {
    Write-Host "Migration failed. Check psql output above." -ForegroundColor Red
}
