$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $ProjectRoot "venv"
$Python = Join-Path $VenvDir "Scripts\python.exe"
$Requirements = Join-Path $ProjectRoot "backend\requirements.txt"
$HostAddress = "127.0.0.1"
$Port = "8080"
$RequiredPython = "3.12"

Set-Location -LiteralPath $ProjectRoot

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "Creating Python $RequiredPython virtual environment..." -ForegroundColor Cyan

    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -$RequiredPython -m venv $VenvDir
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $PythonVersion = (& python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
        if ($PythonVersion -ne $RequiredPython) {
            Write-Host "Found Python $PythonVersion, but this project needs Python $RequiredPython." -ForegroundColor Red
            exit 1
        }
        & python -m venv $VenvDir
    }
    else {
        Write-Host "Python was not found. Install Python 3 and try again." -ForegroundColor Red
        exit 1
    }
}

$VenvPythonVersion = (& $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
if ($VenvPythonVersion -ne $RequiredPython) {
    Write-Host "The existing venv uses Python $VenvPythonVersion, but this project needs Python $RequiredPython." -ForegroundColor Red
    Write-Host "Delete the venv folder and run this script again to recreate it with Python $RequiredPython." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path -LiteralPath $Requirements)) {
    Write-Host "Requirements file not found: $Requirements" -ForegroundColor Red
    exit 1
}

Write-Host "Installing requirements..." -ForegroundColor Cyan
& $Python -m pip install --upgrade pip
& $Python -m pip install -r $Requirements

Write-Host ""
Write-Host "Starting server..." -ForegroundColor Cyan
Write-Host "App:     http://$HostAddress`:$Port"
Write-Host "Swagger: http://$HostAddress`:$Port/docs"
Write-Host ""

& $Python -m uvicorn backend.app.main:app --host $HostAddress --port $Port --reload
