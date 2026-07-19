$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    $Python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $Python) {
        $Python = Get-Command py -ErrorAction SilentlyContinue
    }
    if (-not $Python) {
        Write-Host "Python 3.10 or newer is required." -ForegroundColor Red
        Write-Host "Install Python from https://www.python.org/downloads/ and run this file again."
        exit 1
    }
    Write-Host "Preparing SV Studio for first use..."
    & $Python.Source -m venv (Join-Path $ProjectRoot ".venv")
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
}

Set-Location $ProjectRoot
& $VenvPython -m svstudio.main
