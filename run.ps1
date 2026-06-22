$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot "venv\Scripts\python.exe"
$AppHost = "127.0.0.1"
$AppPort = "8080"

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "Could not find the project virtual environment at:" -ForegroundColor Red
    Write-Host "  $Python" -ForegroundColor Red
    Write-Host ""
    Write-Host "Create or restore the venv first, then run this script again."
    exit 1
}

Set-Location -LiteralPath $ProjectRoot

Write-Host "Starting Mercedes trip planner..." -ForegroundColor Cyan
Write-Host "App:     http://$AppHost`:$AppPort"
Write-Host "Swagger: http://$AppHost`:$AppPort/docs"
Write-Host ""
Write-Host "Press Ctrl+C to stop the server."
Write-Host ""

& $Python -m uvicorn backend.app.main:app --host $AppHost --port $AppPort --reload
