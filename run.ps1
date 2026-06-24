$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $ProjectRoot "venv"
$Python = Join-Path $VenvDir "Scripts\python.exe"
$Requirements = Join-Path $ProjectRoot "backend\requirements.txt"
$DevRequirements = Join-Path $ProjectRoot "backend\requirements-dev.txt"
$AppHost = "127.0.0.1"
$AppPort = "8080"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Command failed with exit code $LASTEXITCODE." -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

function Install-BackendDependencies {
    if (-not (Test-Path -LiteralPath $Requirements)) {
        Write-Host "Could not find backend requirements at: $Requirements" -ForegroundColor Red
        exit 1
    }

    Write-Host "Installing backend dependencies..." -ForegroundColor Yellow
    Invoke-Checked { & $Python -m pip install --upgrade pip setuptools wheel }
    Invoke-Checked { & $Python -m pip install -r $Requirements }

    if (Test-Path -LiteralPath $DevRequirements) {
        Invoke-Checked { & $Python -m pip install -r $DevRequirements }
    }
}

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "Project virtual environment not found. Setting it up..." -ForegroundColor Yellow

    $SystemPython = Get-Command py -ErrorAction SilentlyContinue
    if ($SystemPython) {
        Invoke-Checked { & py -3 -m venv $VenvDir }
    }
    else {
        $SystemPython = Get-Command python -ErrorAction SilentlyContinue
        if (-not $SystemPython) {
            Write-Host "Could not find Python. Install Python 3, then run this script again." -ForegroundColor Red
            exit 1
        }
        Invoke-Checked { & python -m venv $VenvDir }
    }

    if (-not (Test-Path -LiteralPath $Python)) {
        Write-Host "Virtual environment setup failed: $Python was not created." -ForegroundColor Red
        exit 1
    }

    Install-BackendDependencies
}

& $Python -c "import uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Virtual environment exists, but backend dependencies are missing." -ForegroundColor Yellow
    Install-BackendDependencies
}

& $Python -c "import uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "uvicorn is still missing after installing dependencies." -ForegroundColor Red
    Write-Host "Python used: $Python" -ForegroundColor Red
    exit 1
}

Set-Location -LiteralPath $ProjectRoot

Write-Host "Starting Mercedes trip planner..." -ForegroundColor Cyan
Write-Host "Python:  $Python"
Write-Host "App:     http://$AppHost`:$AppPort"
Write-Host "Swagger: http://$AppHost`:$AppPort/docs"
Write-Host ""
Write-Host "Press Ctrl+C to stop the server."
Write-Host ""

Invoke-Checked { & $Python -m uvicorn backend.app.main:app --host $AppHost --port $AppPort --reload }
