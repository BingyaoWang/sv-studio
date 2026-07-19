param(
    [string]$Version = "0.2.0",
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$DistRoot = Join-Path $ProjectRoot "dist"
$WorkRoot = Join-Path $ProjectRoot "build\pyinstaller"
$SpecRoot = Join-Path $ProjectRoot "build"
$PackageDir = Join-Path $DistRoot "SVStudio"
$Archive = Join-Path $DistRoot "SVStudio-Windows-x64-v$Version.zip"

if (Test-Path $VenvPython) {
    $Python = $VenvPython
} else {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $PythonCommand) {
        Write-Host "Python 3.10 or newer is required for packaging." -ForegroundColor Red
        exit 1
    }
    $Python = $PythonCommand.Source
}

if (-not $SkipInstall) {
    & $Python -m pip install -r (Join-Path $ProjectRoot "requirements-dev.txt")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Building SV Studio v$Version..." -ForegroundColor Cyan
& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name SVStudio `
    --distpath $DistRoot `
    --workpath $WorkRoot `
    --specpath $SpecRoot `
    --add-data "$ProjectRoot\examples;examples" `
    --add-data "$ProjectRoot\tools\setup_open_source_uvm.ps1;tools" `
    (Join-Path $ProjectRoot "sv_studio.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Copy-Item -LiteralPath (Join-Path $ProjectRoot "README.md") -Destination $PackageDir -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "LICENSE") -Destination $PackageDir -Force

if (Test-Path -LiteralPath $Archive) {
    $ResolvedArchive = (Resolve-Path -LiteralPath $Archive).Path
    if (-not $ResolvedArchive.StartsWith($DistRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to overwrite an archive outside the dist directory."
    }
    Remove-Item -LiteralPath $ResolvedArchive -Force
}
Compress-Archive -Path (Join-Path $PackageDir "*") -DestinationPath $Archive -CompressionLevel Optimal

$SizeMb = [math]::Round((Get-Item -LiteralPath $Archive).Length / 1MB, 1)
Write-Host "Package ready: $Archive ($SizeMb MB)" -ForegroundColor Green
