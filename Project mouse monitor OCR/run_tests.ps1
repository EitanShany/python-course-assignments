param(
    [ValidateSet("Quick", "Full")]
    [string]$Mode = "Quick"
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

    $VenvPython = Join-Path $ProjectFolder ".venv\Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) {
        throw "Virtual environment Python was not found: $VenvPython"
    }

    if ($Mode -eq "Full") {
        Write-Host "Running full QA check..." -ForegroundColor Cyan
        & $VenvPython -m pytest -q
    }
    else {
        Write-Host "Running quick QA check..." -ForegroundColor Cyan
        & $VenvPython -m pytest -m "not full" -q
    }
}
catch {
    Write-Host ""
    Write-Host "Test run failed:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
