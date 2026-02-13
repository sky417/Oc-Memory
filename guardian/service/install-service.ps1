# OC-Guardian Windows Service Installer
# Usage: .\install-service.ps1 [-Action install|uninstall|status]
# Requires: Administrator privileges

param(
    [ValidateSet("install", "uninstall", "status")]
    [string]$Action = "install"
)

$ErrorActionPreference = "Stop"
$ServiceName = "OC-Guardian"
$DisplayName = "OC-Guardian Process Manager"
$Description = "Manages OpenClaw and OC-Memory processes"

# Find binary
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$BinaryPath = Join-Path $ProjectRoot "guardian\target\release\oc-guardian.exe"
$ConfigPath = Join-Path $ProjectRoot "guardian\guardian.toml"

# Check admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

function Install-GuardianService {
    if (-not $isAdmin) {
        Write-Host "ERROR: Administrator privileges required." -ForegroundColor Red
        Write-Host "Run PowerShell as Administrator and try again." -ForegroundColor Yellow
        exit 1
    }

    if (-not (Test-Path $BinaryPath)) {
        Write-Host "ERROR: Binary not found: $BinaryPath" -ForegroundColor Red
        Write-Host "Build first: cargo build --release" -ForegroundColor Yellow
        exit 1
    }

    # Create NSSM-based service or use sc.exe with a wrapper
    # Since Windows services require specific APIs, we use a scheduled task approach
    Write-Host "Installing OC-Guardian as a Scheduled Task..." -ForegroundColor Yellow

    # Remove existing task if present
    Unregister-ScheduledTask -TaskName $ServiceName -Confirm:$false -ErrorAction SilentlyContinue

    # Create action
    $taskAction = New-ScheduledTaskAction -Execute $BinaryPath -Argument "start --config `"$ConfigPath`"" -WorkingDirectory (Split-Path $ConfigPath)

    # Create trigger (at startup)
    $taskTrigger = New-ScheduledTaskTrigger -AtStartup

    # Create settings
    $taskSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 365)

    # Register task
    Register-ScheduledTask -TaskName $ServiceName -Action $taskAction -Trigger $taskTrigger -Settings $taskSettings -Description $Description -RunLevel Highest -Force

    Write-Host "  Task registered: $ServiceName" -ForegroundColor Green
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor Yellow
    Write-Host "  Start-ScheduledTask -TaskName '$ServiceName'       - Start"
    Write-Host "  Stop-ScheduledTask -TaskName '$ServiceName'        - Stop"
    Write-Host "  Get-ScheduledTask -TaskName '$ServiceName'         - Status"
    Write-Host "  Unregister-ScheduledTask -TaskName '$ServiceName'  - Remove"
}

function Uninstall-GuardianService {
    if (-not $isAdmin) {
        Write-Host "ERROR: Administrator privileges required." -ForegroundColor Red
        exit 1
    }

    Write-Host "Uninstalling OC-Guardian..." -ForegroundColor Yellow

    # Stop if running
    Stop-ScheduledTask -TaskName $ServiceName -ErrorAction SilentlyContinue

    # Remove
    Unregister-ScheduledTask -TaskName $ServiceName -Confirm:$false -ErrorAction SilentlyContinue

    Write-Host "  Task removed: $ServiceName" -ForegroundColor Green
}

function Get-GuardianStatus {
    try {
        $task = Get-ScheduledTask -TaskName $ServiceName -ErrorAction Stop
        Write-Host "Service: $ServiceName" -ForegroundColor Cyan
        Write-Host "  State:    $($task.State)" -ForegroundColor $(if ($task.State -eq "Running") { "Green" } else { "Yellow" })
        Write-Host "  Path:     $BinaryPath"
        Write-Host "  Config:   $ConfigPath"
    } catch {
        Write-Host "Service '$ServiceName' is not installed." -ForegroundColor Yellow
    }
}

# Execute
switch ($Action) {
    "install"   { Install-GuardianService }
    "uninstall" { Uninstall-GuardianService }
    "status"    { Get-GuardianStatus }
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Green
