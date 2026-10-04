<#
.SYNOPSIS
    Install monitor-com as a visible Windows service.

.DESCRIPTION
    Installs the agent as a Windows service named "MonitorCom". The service is
    fully visible in services.msc and Task Manager — this tool does not hide
    itself. Consent must already be recorded (run the agent once interactively
    first, or set consent.preacknowledged in the config) or the service will
    refuse to collect.

    Run from an elevated PowerShell prompt.

.PARAMETER ConfigPath
    Path to config.yaml. Stored in the service environment so the agent can find
    it at startup.

.PARAMETER PythonExe
    Path to the Python executable to run the service with. Defaults to the
    Python on PATH.

.EXAMPLE
    .\install_service.ps1 -ConfigPath C:\ProgramData\monitor-com\config.yaml
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$ConfigPath,

    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ConfigPath)) {
    throw "Config file not found: $ConfigPath"
}

$resolvedConfig = (Resolve-Path $ConfigPath).Path

Write-Host "Setting MONITOR_COM_CONFIG (machine scope) to $resolvedConfig"
[Environment]::SetEnvironmentVariable("MONITOR_COM_CONFIG", $resolvedConfig, "Machine")
$env:MONITOR_COM_CONFIG = $resolvedConfig

Write-Host "Installing the MonitorCom service..."
& $PythonExe -m monitor_agent.service --startup auto install

Write-Host "Starting the MonitorCom service..."
& $PythonExe -m monitor_agent.service start

Write-Host ""
Write-Host "Done. The service 'MonitorCom' is installed and visible in services.msc."
Write-Host "Reminder: ensure users have been given notice and a lawful basis exists."
Write-Host "See docs/ACCEPTABLE_USE.md."
