param(
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"

try {
    $ProjectFolder = if ($PSScriptRoot) {
        $PSScriptRoot
    }
    else {
        Split-Path -Parent $MyInvocation.MyCommand.Path
    }
    Set-Location $ProjectFolder

    Write-Host "Starting Mouse Monitor OCR..." -ForegroundColor Cyan
    Write-Host "Project folder: $ProjectFolder"

    $VenvPython = Join-Path $ProjectFolder ".venv\Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) {
        Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
        $SystemPython = (Get-Command python -ErrorAction Stop).Source
        & $SystemPython -m venv .venv
    }

    if (-not (Test-Path $VenvPython)) {
        throw "Virtual environment Python was not created: $VenvPython"
    }

    Write-Host "Using Python: $VenvPython"

    Write-Host "Installing/updating required Python packages..." -ForegroundColor Yellow
    & $VenvPython -m pip install -r requirements.txt

    Write-Host "Checking Streamlit..." -ForegroundColor Yellow
    & $VenvPython -m streamlit --version

    Write-Host "Stopping older Mouse Monitor OCR Python processes..." -ForegroundColor Yellow
    $OldProjectProcesses = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
        $_.Id -ne $PID -and $_.Path -eq $VenvPython
    }
    foreach ($Process in $OldProjectProcesses) {
        try {
            Stop-Process -Id $Process.Id -Force -ErrorAction Stop
            Write-Host "Stopped old process $($Process.Id)." -ForegroundColor DarkYellow
        }
        catch {
            Write-Host "Could not stop old process $($Process.Id): $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }

    if ($CheckOnly) {
        Write-Host "Check complete. The app was not started because -CheckOnly was used." -ForegroundColor Green
    }
    else {
        Write-Host "Opening the app. Keep this window open while using it." -ForegroundColor Green
        Write-Host "The app will run on http://localhost:8501" -ForegroundColor Green
        Write-Host "If the browser does not open automatically, copy the Local URL printed below."
        & $VenvPython -m streamlit run app.py --server.port 8501
    }
}
catch {
    Write-Host ""
    Write-Host "Mouse Monitor OCR failed to start:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}
finally {
    Write-Host ""
    Read-Host "Press Enter to close this window"
}
S