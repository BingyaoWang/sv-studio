param(
    [string]$Version = "0.4.0",
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
$Installer = Join-Path $DistRoot "SVStudio-Setup-x64-v$Version.exe"
$AppIcon = Join-Path $ProjectRoot "assets\branding\sv-studio.ico"
$VersionInfo = Join-Path $ProjectRoot "tools\windows_version_info.txt"
$InstallerScript = Join-Path $ProjectRoot "tools\svstudio-installer.iss"

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
    --icon $AppIcon `
    --version-file $VersionInfo `
    --distpath $DistRoot `
    --workpath $WorkRoot `
    --specpath $SpecRoot `
    --add-data "$ProjectRoot\examples\systemverilog\.svstudio.json;examples\systemverilog" `
    --add-data "$ProjectRoot\examples\systemverilog\rtl;examples\systemverilog\rtl" `
    --add-data "$ProjectRoot\examples\systemverilog\tb;examples\systemverilog\tb" `
    --add-data "$ProjectRoot\examples\uvm_counter\.svstudio.json;examples\uvm_counter" `
    --add-data "$ProjectRoot\examples\uvm_counter\README.md;examples\uvm_counter" `
    --add-data "$ProjectRoot\examples\uvm_counter\rtl;examples\uvm_counter\rtl" `
    --add-data "$ProjectRoot\examples\uvm_counter\tb;examples\uvm_counter\tb" `
    --add-data "$ProjectRoot\assets\branding\sv-studio-logo.png;assets\branding" `
    --add-data "$ProjectRoot\assets\branding\sv-studio.ico;assets\branding" `
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

$InnoCandidates = @(
    $env:ISCC_PATH,
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

$InnoCompiler = $InnoCandidates | Select-Object -First 1
if (-not $InnoCompiler) {
    $InnoCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($InnoCommand) {
        $InnoCompiler = $InnoCommand.Source
    }
}
if (-not $InnoCompiler) {
    throw "Inno Setup 6 is required to build the Windows installer. Install JRSoftware.InnoSetup with winget, then run this script again."
}

Write-Host "Building Windows installer..." -ForegroundColor Cyan
& $InnoCompiler `
    "/DMyAppVersion=$Version" `
    "/DMySourceDir=$PackageDir" `
    "/DMyOutputDir=$DistRoot" `
    $InstallerScript
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$InstallerSizeMb = [math]::Round((Get-Item -LiteralPath $Installer).Length / 1MB, 1)
Write-Host "Installer ready: $Installer ($InstallerSizeMb MB)" -ForegroundColor Green
