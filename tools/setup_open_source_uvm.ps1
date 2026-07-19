param(
    [Parameter(Mandatory = $false)]
    [string]$ProjectRoot = (Get-Location).Path
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path $ProjectRoot).Path

Write-Host ""
Write-Host "SV Studio — Free SystemVerilog + UVM Setup" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor DarkGray
Write-Host "This installs only open-source software:"
Write-Host "  • Verilator (GPL-3.0 / Artistic-2.0)"
Write-Host "  • CHIPS Alliance UVM for Verilator (Apache-2.0)"
Write-Host "No EDA license or license server is required." -ForegroundColor Green
Write-Host ""

$Wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $Wsl) {
    Write-Host "WSL is required on Windows." -ForegroundColor Red
    Write-Host "Run 'wsl --install -d Ubuntu' in an Administrator terminal, restart, then retry."
    exit 1
}

$WslProject = (& wsl.exe -d Ubuntu -- wslpath -a $ProjectRoot).Trim()
if (-not $WslProject) {
    Write-Host "Could not translate the project folder into WSL." -ForegroundColor Red
    exit 1
}

Write-Host "Installing build prerequisites in Ubuntu..." -ForegroundColor Yellow
& wsl.exe -d Ubuntu -- bash -lc "sudo apt-get update && sudo apt-get install -y git autoconf flex bison help2man perl make g++ ccache libfl-dev zlib1g-dev z3"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Building current stable Verilator locally (this can take several minutes)..." -ForegroundColor Yellow
$BuildScript = @'
set -euo pipefail
mkdir -p "$HOME/.cache/sv-studio" "$HOME/.local/sv-studio"
if [ ! -d "$HOME/.cache/sv-studio/verilator-src/.git" ]; then
  git clone --depth 1 --branch stable https://github.com/verilator/verilator.git "$HOME/.cache/sv-studio/verilator-src"
else
  git -C "$HOME/.cache/sv-studio/verilator-src" fetch --depth 1 origin stable
  git -C "$HOME/.cache/sv-studio/verilator-src" reset --hard origin/stable
fi
cd "$HOME/.cache/sv-studio/verilator-src"
autoconf
./configure --prefix="$HOME/.local/sv-studio/verilator"
make -j"$(nproc)"
make install
"$HOME/.local/sv-studio/verilator/bin/verilator" --version
z3 --version
'@
& wsl.exe -d Ubuntu -- bash -lc $BuildScript
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Downloading the UVM library for Verilator..." -ForegroundColor Yellow
$UvmScript = @"
set -euo pipefail
mkdir -p '$WslProject/tools'
if [ ! -d '$WslProject/tools/uvm-verilator/.git' ]; then
  git clone --depth 1 https://github.com/chipsalliance/uvm-verilator.git '$WslProject/tools/uvm-verilator'
else
  git -C '$WslProject/tools/uvm-verilator' pull --ff-only
fi
test -f '$WslProject/tools/uvm-verilator/src/uvm.sv'
"@
& wsl.exe -d Ubuntu -- bash -lc $UvmScript
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Complete — the free UVM toolchain is ready." -ForegroundColor Green
Write-Host "Return to SV Studio, open Toolchains, and click Refresh Status."
