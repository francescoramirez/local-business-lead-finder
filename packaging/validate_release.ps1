<#
.SYNOPSIS
  Validate a local LeadFinder Windows build without publishing it.
#>
param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Resolve-Python {
    if ($env:LEADFINDER_PYTHON -and (Test-Path $env:LEADFINDER_PYTHON)) {
        return $env:LEADFINDER_PYTHON
    }
    $venvPy = Join-Path $env:TEMP "leadfinder-official-venv-3.12\Scripts\python.exe"
    if (Test-Path $venvPy) { return $venvPy }
    $p312 = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    if (Test-Path $p312) { return $p312 }
    return "python"
}

$Python = Resolve-Python

if (-not $Version) {
    $Version = & $Python -c "from leadfinder import __version__; print(__version__)"
}

$App = Join-Path $Root "dist\LeadFinder\LeadFinder.exe"
$License = Join-Path $Root "dist\LeadFinder\LICENSE"
$Internal = Join-Path $Root "dist\LeadFinder\_internal"
$Release = Join-Path $Root "dist\release"
$Zip = Join-Path $Release "LeadFinder-$Version-win64-standalone.zip"
$Installer = Join-Path $Release "LeadFinder-Setup-$Version.exe"
$Manifest = Join-Path $Release "release-manifest.json"
$Hashes = Join-Path $Release "SHA256SUMS.txt"

$failed = $false
function Need($Path, $Label) {
    if (Test-Path $Path) {
        Write-Host "OK $Label"
    } else {
        Write-Warning "MISSING $Label ($Path)"
        $script:failed = $true
    }
}

Need $App "LeadFinder.exe"
Need $License "LICENSE in app folder"
Need $Internal "_internal"
Need $Zip "standalone ZIP"
Need $Manifest "release-manifest.json"
Need $Hashes "SHA256SUMS.txt"
if (Test-Path $Installer) {
    Write-Host "OK installer"
} else {
    Write-Host "NOTE installer not present (NOT_AVAILABLE is allowed if Inno Setup 6 is missing)."
}

$envHits = Get-ChildItem -Recurse -Force (Join-Path $Root "dist\LeadFinder") -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq ".env" -or $_.Extension -in @(".db", ".sqlite", ".log") }
if ($envHits) {
    Write-Warning "Forbidden data files in app folder"
    $failed = $true
} else {
    Write-Host "OK no .env/.db/.log in app folder"
}

& $Python packaging/scan_artifact.py --root (Join-Path $Root "dist\LeadFinder")
if ($LASTEXITCODE -ne 0) { $failed = $true }

if ($failed) { throw "Release validation failed." }
Write-Host "Release validation passed."
