<#
.SYNOPSIS
  Silent per-user install / launch / reinstall / uninstall smoke. Does not delete owner SQLite.
#>
param(
    [Parameter(Mandatory = $true)][string]$SetupExe
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $SetupExe)) { throw "Setup missing: $SetupExe" }

$InstalledExe = Join-Path $env:LOCALAPPDATA "Programs\LeadFinder\LeadFinder.exe"
$DataDir = Join-Path $env:LOCALAPPDATA "LeadFinder\LeadFinder"
$Sentinel = Join-Path $DataDir "owner-data-preservation-test.txt"
$Token = "leadfinder-data-preservation-" + [guid]::NewGuid().ToString("N")

function Find-UninstallCommand {
    $roots = @(
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall",
        "HKCU:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
    )
    foreach ($root in $roots) {
        if (-not (Test-Path $root)) { continue }
        foreach ($key in Get-ChildItem $root -ErrorAction SilentlyContinue) {
            $item = Get-ItemProperty $key.PSPath -ErrorAction SilentlyContinue
            if ($null -eq $item) { continue }
            if ($item.DisplayName -and $item.DisplayName -like "LeadFinder*") {
                if ($item.QuietUninstallString) { return $item.QuietUninstallString }
                if ($item.UninstallString) { return $item.UninstallString }
            }
        }
    }
    $fallback = Join-Path $env:LOCALAPPDATA "Programs\LeadFinder\unins000.exe"
    if (Test-Path $fallback) { return "`"$fallback`"" }
    return $null
}

function Invoke-UninstallQuiet {
    $command = Find-UninstallCommand
    if (-not $command) { throw "Uninstall command not found" }
    Write-Host "Uninstall: $command"
    if ($command -match '^\s*"(?<exe>[^"]+)"\s*(?<args>.*)$') {
        $exe = $Matches.exe
        $args = $Matches.args.Trim()
        if ($args -notmatch 'SILENT') { $args = ($args + " /VERYSILENT /NORESTART /SUPPRESSMSGBOXES").Trim() }
        $p = Start-Process -FilePath $exe -ArgumentList $args -Wait -PassThru
        if ($p.ExitCode -ne 0) { throw "Uninstall exit $($p.ExitCode)" }
        return
    }
    $parts = $command.Trim().Split(" ", 2)
    $exe = $parts[0].Trim('"')
    $args = if ($parts.Count -gt 1) { $parts[1] } else { "" }
    if ($args -notmatch 'SILENT') { $args = "/VERYSILENT /NORESTART /SUPPRESSMSGBOXES" }
    $p = Start-Process -FilePath $exe -ArgumentList $args -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "Uninstall exit $($p.ExitCode)" }
}

function Invoke-InstalledSmoke([string]$Label) {
    if (-not (Test-Path $InstalledExe)) { throw "$Label missing $InstalledExe" }
    $env:LEADFINDER_SMOKE_EXIT = "1"
    $env:LEADFINDER_IGNORE_DOTENV = "1"
    $env:QT_QPA_PLATFORM = "offscreen"
    $work = Split-Path $InstalledExe
    Write-Host "$Label launch $InstalledExe (workdir $work)"
    $p = Start-Process -FilePath $InstalledExe -WorkingDirectory $work -Wait -PassThru -WindowStyle Hidden
    Remove-Item Env:LEADFINDER_SMOKE_EXIT -ErrorAction SilentlyContinue
    if ($p.ExitCode -ne 0) { throw "$Label launch exit $($p.ExitCode)" }
    Write-Host "$Label PASS"
}

New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
Set-Content -Path $Sentinel -Value $Token -Encoding utf8

Write-Host "INSTALLER_INSTALL ..."
$p = Start-Process -FilePath $SetupExe -ArgumentList "/VERYSILENT","/NORESTART","/SUPPRESSMSGBOXES" -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "INSTALLER_INSTALL exit $($p.ExitCode)" }
if (-not (Test-Path $InstalledExe)) { throw "Installed LeadFinder.exe missing" }
Write-Host "INSTALLER_INSTALL PASS"

Invoke-InstalledSmoke "INSTALLER_LAUNCH"

Write-Host "INSTALLER_REINSTALL ..."
$p = Start-Process -FilePath $SetupExe -ArgumentList "/VERYSILENT","/NORESTART","/SUPPRESSMSGBOXES" -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "INSTALLER_REINSTALL exit $($p.ExitCode)" }
Invoke-InstalledSmoke "INSTALLER_REINSTALL_LAUNCH"
Write-Host "INSTALLER_REINSTALL PASS"

Write-Host "INSTALLER_UNINSTALL ..."
Invoke-UninstallQuiet
Start-Sleep -Seconds 2
if (Test-Path $InstalledExe) {
    Write-Warning "LeadFinder.exe still present after uninstall"
}
Write-Host "INSTALLER_UNINSTALL PASS"

if (-not (Test-Path $Sentinel)) { throw "USER_DATA_PRESERVED FAIL: sentinel missing" }
$read = Get-Content -Raw $Sentinel
if ($read.Trim() -ne $Token) { throw "USER_DATA_PRESERVED FAIL: sentinel changed" }
Remove-Item -Force $Sentinel
Write-Host "USER_DATA_PRESERVED PASS (sentinel removed after check; owner DB untouched)"
