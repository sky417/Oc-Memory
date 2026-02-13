# OC-Memory + Guardian Install Script (Windows)
# Usage: .\scripts\install.ps1 [-SkipPython] [-SkipBuild]

param(
    [switch]$SkipPython,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  OC-Memory + Guardian Install" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot"
Write-Host ""

# =============================================================================
# 1. Check and Install Rust
# =============================================================================

Write-Host "--- Checking Rust ---" -ForegroundColor Yellow
$RustInstalled = $false
try {
    $rustVersion = & rustc --version 2>&1
    $cargoVersion = & cargo --version 2>&1
    Write-Host "  Rust:  $rustVersion" -ForegroundColor Green
    Write-Host "  Cargo: $cargoVersion" -ForegroundColor Green
    $RustInstalled = $true
} catch {
    Write-Host "  Rust is not installed." -ForegroundColor Red
    $answer = Read-Host "Install Rust via winget? [Y/n]"
    if ($answer -ne "n" -and $answer -ne "N") {
        Write-Host "  Installing Rust..." -ForegroundColor Yellow
        winget install Rustlang.Rustup --accept-source-agreements --accept-package-agreements
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        $RustInstalled = $true
    } else {
        Write-Host "  Rust is required for Guardian. Exiting." -ForegroundColor Red
        exit 1
    }
}
Write-Host ""

# =============================================================================
# 2. Check Python
# =============================================================================

Write-Host "--- Checking Python ---" -ForegroundColor Yellow
$PythonCmd = $null
try {
    $pyVersion = & python --version 2>&1
    Write-Host "  Python: $pyVersion" -ForegroundColor Green
    $PythonCmd = "python"
} catch {
    try {
        $pyVersion = & python3 --version 2>&1
        Write-Host "  Python: $pyVersion" -ForegroundColor Green
        $PythonCmd = "python3"
    } catch {
        Write-Host "  WARNING: Python not found. OC-Memory features will be limited." -ForegroundColor Yellow
        Write-Host "  Install Python 3.8+ for full functionality." -ForegroundColor Yellow
    }
}
Write-Host ""

# =============================================================================
# 3. Install Python Dependencies
# =============================================================================

if (-not $SkipPython -and $PythonCmd) {
    Write-Host "--- Installing Python Dependencies ---" -ForegroundColor Yellow
    $reqFile = Join-Path $ProjectRoot "requirements.txt"
    if (Test-Path $reqFile) {
        try {
            & $PythonCmd -m pip install -r $reqFile 2>$null
            Write-Host "  Python dependencies installed." -ForegroundColor Green
        } catch {
            Write-Host "  WARNING: Failed to install Python dependencies." -ForegroundColor Yellow
        }
    } else {
        Write-Host "  No requirements.txt found, skipping." -ForegroundColor DarkGray
    }
    Write-Host ""
}

# =============================================================================
# 4. Build Guardian
# =============================================================================

if (-not $SkipBuild) {
    Write-Host "--- Building Guardian ---" -ForegroundColor Yellow
    Push-Location (Join-Path $ProjectRoot "guardian")

    cargo build --release 2>&1

    $binary = "target\release\oc-guardian.exe"
    if (Test-Path $binary) {
        $size = (Get-Item $binary).Length / 1MB
        Write-Host ("  Binary: $binary ({0:N1} MB)" -f $size) -ForegroundColor Green

        # Copy to project root
        Copy-Item $binary (Join-Path $ProjectRoot "oc-guardian.exe")
        Write-Host "  Copied to: $ProjectRoot\oc-guardian.exe" -ForegroundColor Green
    }

    Pop-Location
    Write-Host ""
}

# =============================================================================
# 5. Auto-detect and Generate Configuration
# =============================================================================

Write-Host "--- Configuration Setup ---" -ForegroundColor Yellow

# Detect OpenClaw paths
$OpenClawDir = $null
$possiblePaths = @(
    (Join-Path $env:USERPROFILE ".openclaw"),
    (Join-Path $env:APPDATA "openclaw"),
    (Join-Path $env:LOCALAPPDATA "openclaw")
)

foreach ($path in $possiblePaths) {
    if (Test-Path $path) {
        $OpenClawDir = $path
        Write-Host "  OpenClaw detected: $OpenClawDir" -ForegroundColor Green
        break
    }
}

if (-not $OpenClawDir) {
    Write-Host "  OpenClaw not detected (will use defaults)" -ForegroundColor DarkGray
}

# Generate guardian.toml if not exists
$guardianToml = Join-Path $ProjectRoot "guardian\guardian.toml"
$guardianExample = Join-Path $ProjectRoot "guardian\guardian.toml.example"
if (-not (Test-Path $guardianToml) -and (Test-Path $guardianExample)) {
    Copy-Item $guardianExample $guardianToml
    Write-Host "  Created guardian.toml from example" -ForegroundColor Green

    # Auto-fill detected paths
    if ($OpenClawDir) {
        $content = Get-Content $guardianToml -Raw
        $content = $content -replace "~/.openclaw", $OpenClawDir.Replace("\", "/")
        Set-Content $guardianToml $content
        Write-Host "  Auto-filled OpenClaw paths" -ForegroundColor Green
    }
}

# Generate config.yaml if not exists
$configYaml = Join-Path $ProjectRoot "config.yaml"
$configExample = Join-Path $ProjectRoot "config.example.yaml"
if (-not (Test-Path $configYaml) -and (Test-Path $configExample)) {
    Copy-Item $configExample $configYaml
    Write-Host "  Created config.yaml from example" -ForegroundColor Green
}

Write-Host ""

# =============================================================================
# 6. Create log directories
# =============================================================================

Write-Host "--- Creating Directories ---" -ForegroundColor Yellow
$logsDir = Join-Path $ProjectRoot "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}
Write-Host "  Created logs/" -ForegroundColor Green

if ($OpenClawDir) {
    $memoryDir = Join-Path $OpenClawDir "workspace\memory"
    if (-not (Test-Path $memoryDir)) {
        New-Item -ItemType Directory -Path $memoryDir -Force | Out-Null
    }
    Write-Host "  Ensured $memoryDir" -ForegroundColor Green
}

Write-Host ""

# =============================================================================
# 7. Verify Installation
# =============================================================================

Write-Host "--- Verification ---" -ForegroundColor Yellow

$guardianBin = Join-Path $ProjectRoot "oc-guardian.exe"
if (Test-Path $guardianBin) {
    Write-Host "  Guardian binary: OK" -ForegroundColor Green
    try {
        & $guardianBin --version 2>$null
    } catch {
        Write-Host "    (version check skipped)" -ForegroundColor DarkGray
    }
} else {
    Write-Host "  Guardian binary: MISSING" -ForegroundColor Red
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  Install Complete!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Edit guardian\guardian.toml (process paths)"
Write-Host "  2. Edit config.yaml (API keys, if using OC-Memory)"
Write-Host "  3. Run: .\oc-guardian.exe start"
Write-Host ""
Write-Host "Quick commands:" -ForegroundColor Yellow
Write-Host "  .\oc-guardian.exe start    - Start all processes"
Write-Host "  .\oc-guardian.exe status   - Check status"
Write-Host "  .\oc-guardian.exe stop     - Stop all processes"
Write-Host "  .\oc-guardian.exe --help   - Full help"
Write-Host ""
