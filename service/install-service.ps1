# OC-Memory Service Installer for Windows
# Creates a Scheduled Task to run the memory observer at login

param(
    [string]$InstallDir = "$env:LOCALAPPDATA\oc-memory",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$TaskName = "OC-Memory Observer"
$ProjectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Write-Info { Write-Host "[INFO] $args" -ForegroundColor Green }
function Write-Warn { Write-Host "[WARN] $args" -ForegroundColor Yellow }
function Write-Err  { Write-Host "[ERROR] $args" -ForegroundColor Red }

# Uninstall
if ($Uninstall) {
    Write-Info "Removing OC-Memory Scheduled Task..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Info "Removing install directory: $InstallDir"
    if (Test-Path $InstallDir) { Remove-Item -Recurse -Force $InstallDir }
    Write-Info "Uninstall complete."
    exit 0
}

# Install
Write-Info "OC-Memory Service Installer (Windows)"
Write-Info ""

# Copy files
Write-Info "Installing OC-Memory to $InstallDir..."
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -Recurse -Force "$ProjectDir\lib" "$InstallDir\"
Copy-Item -Force "$ProjectDir\memory_observer.py" "$InstallDir\"
Copy-Item -Force "$ProjectDir\requirements.txt" "$InstallDir\"

if (Test-Path "$ProjectDir\config.yaml") {
    Copy-Item -Force "$ProjectDir\config.yaml" "$InstallDir\"
}

# Install dependencies
Write-Info "Installing Python dependencies..."
python -m pip install -r "$InstallDir\requirements.txt" --quiet 2>$null

# Find Python
$PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonPath) {
    $PythonPath = (Get-Command python3 -ErrorAction SilentlyContinue).Source
}
if (-not $PythonPath) {
    Write-Err "Python not found in PATH"
    exit 1
}

# Create Scheduled Task
Write-Info "Creating Scheduled Task: $TaskName"

$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "memory_observer.py" `
    -WorkingDirectory $InstallDir

$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 365)

# Remove existing task if present
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "OC-Memory Observer - External observational memory for OpenClaw" `
    -RunLevel Limited

# Start the task now
Write-Info "Starting task..."
Start-ScheduledTask -TaskName $TaskName

Write-Info ""
Write-Info "Installation complete!"
Write-Info "Commands:"
Write-Info "  Status:    Get-ScheduledTask -TaskName '$TaskName'"
Write-Info "  Stop:      Stop-ScheduledTask -TaskName '$TaskName'"
Write-Info "  Uninstall: .\install-service.ps1 -Uninstall"
