<#
.SYNOPSIS
    Runs Repomedic in local development mode.
.DESCRIPTION
    Starts the Vite React frontend and FastAPI backend (if virtual environment is active).
#>

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  Repomedic Local Development Launcher   " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$FrontendDir = Join-Path $PSScriptRoot "..\frontend"
$BackendDir = Join-Path $PSScriptRoot "..\backend"

if (-Not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "[!] frontend dependencies not found. Installing..." -ForegroundColor Yellow
    npm --prefix $FrontendDir install
}

Write-Host "[*] Starting Vite frontend on http://localhost:5173..." -ForegroundColor Green
Start-Process -FilePath "npm" -ArgumentList "--prefix", "$FrontendDir", "run", "dev"

if (Test-Path (Join-Path $BackendDir "requirements.txt")) {
    Write-Host "[*] Backend scaffold detected at $BackendDir" -ForegroundColor Green
    Write-Host "    To start backend: uvicorn app.main:app --reload --port 8000 (from backend/)" -ForegroundColor DarkGray
}

Write-Host "`n[✓] Frontend launched. Press Enter to exit launcher." -ForegroundColor Cyan
