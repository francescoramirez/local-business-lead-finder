<#
.SYNOPSIS
  Repeatable Windows one-folder build for LeadFinder using Python 3.12 x64.
#>
param(
    [switch]$SkipTests,
    [switch]$SkipInstaller,
    [switch]$SkipPackagedQa
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Resolve-Python312 {
    if ($env:LEADFINDER_PYTHON -and (Test-Path $env:LEADFINDER_PYTHON)) {
        return (Resolve-Path $env:LEADFINDER_PYTHON).Path
    }
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "C:\Python312\python.exe"
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) { return $path }
    }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        $listed = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $listed -and (Test-Path $listed.Trim())) {
            return $listed.Trim()
        }
    }
    throw @"
Official desktop packager requires Python 3.12 x64.
Install Python 3.12 (python.org or winget id Python.Python.3.12) or set LEADFINDER_PYTHON.
Source still supports Python >=3.10. Do not use an ambiguous global 'python' for release builds.
"@
}

function Find-ISCC {
    $cmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $paths = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($path in $paths) {
        if (Test-Path $path) { return $path }
    }
    return $null
}

function Test-TransientLockMessage([string]$Message) {
    $m = $Message.ToLowerInvariant()
    return $m -match 'sharing violation' -or
        $m -match 'being used by another process' -or
        $m -match 'permission denied' -or
        $m -match 'access is denied' -or
        $m -match 'temporarily unavailable' -or
        $m -match 'the process cannot access the file'
}

function Invoke-ExeWithLockRetry {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [int]$Attempts = 3
    )
    $code = 1
    for ($i = 1; $i -le $Attempts; $i++) {
        Write-Host "Launch attempt $i/$Attempts : $Exe"
        try {
            $p = Start-Process -FilePath $Exe -Wait -PassThru -WindowStyle Hidden
            $code = $p.ExitCode
            if ($null -eq $code) { $code = 1 }
            return $code
        } catch {
            $text = $_.Exception.Message
            Write-Warning $text
            if ($i -eq $Attempts -or -not (Test-TransientLockMessage $text)) {
                throw
            }
            Start-Sleep -Seconds (2 * $i)
        }
    }
    return $code
}

function Invoke-CheckedPy([string]$PythonExe, [string]$Args) {
    Write-Host ">> $PythonExe $Args"
    & $PythonExe $Args.Split(" ")
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $PythonExe $Args" }
}

$Python312 = Resolve-Python312
$arch = & $Python312 -c "import sys; print('x64' if sys.maxsize > 2**32 else 'x86')"
if ($arch -ne "x64") { throw "Python 3.12 must be x64. Found $arch at $Python312" }
$pyVer = & $Python312 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($pyVer -ne "3.12") { throw "Official packager must be Python 3.12. Found $pyVer at $Python312" }

$VenvDir = Join-Path $env:TEMP "leadfinder-official-venv-3.12"
$VenvPy = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
    Write-Host "Creating isolated venv $VenvDir"
    & $Python312 -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
}
$Python = $VenvPy

Write-Host "Installing package extras (gui, build, dev) into official venv..."
& $Python -m pip install -U pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
& $Python -m pip install -e ".[gui,build,dev]"
if ($LASTEXITCODE -ne 0) { throw "pip install extras failed" }

$envReport = & $Python -c @"
import platform, sys
from importlib import metadata
try:
    from PySide6.QtCore import qVersion
    qt = qVersion()
except Exception:
    qt = 'unknown'
print('Python', sys.version.replace('\n',' '))
print('executable', sys.executable)
print('architecture', platform.machine(), 'x64' if sys.maxsize>2**32 else 'x86')
print('pip', metadata.version('pip'))
print('PyInstaller', metadata.version('pyinstaller'))
try:
    print('PySide6', metadata.version('PySide6'))
except Exception:
    print('PySide6', metadata.version('PySide6-Essentials'))
print('Qt', qt)
print('Windows', platform.platform())
"@
Write-Host "===== BUILD ENVIRONMENT ====="
Write-Host $envReport
$Iscc = Find-ISCC
if ($Iscc) { Write-Host "Inno Setup $Iscc" } else { Write-Host "Inno Setup 6 not found" }
Write-Host "=============================="

& $Python packaging/make_placeholder_icon.py
if ($LASTEXITCODE -ne 0) { throw "Icon generation failed." }
& $Python packaging/write_version_info.py --output packaging/file_version_info.txt
if ($LASTEXITCODE -ne 0) { throw "VERSIONINFO generation failed." }

if (-not $SkipTests) {
    & $Python -m ruff check .
    if ($LASTEXITCODE -ne 0) { throw "ruff failed" }
    $env:QT_QPA_PLATFORM = "offscreen"
    & $Python -m pytest
    if ($LASTEXITCODE -ne 0) { throw "pytest failed" }
    & $Python -m mypy src/leadfinder
    if ($LASTEXITCODE -ne 0) { throw "mypy failed" }
    & $Python -m compileall src
    if ($LASTEXITCODE -ne 0) { throw "compileall failed" }
}

$Staging = Join-Path $env:TEMP "leadfinder-build"
$StagingDist = Join-Path $Staging "dist"
$StagingWork = Join-Path $Staging "work"
Write-Host "Staging build dir: $Staging"
if (Test-Path $Staging) { Remove-Item -Recurse -Force $Staging }
New-Item -ItemType Directory -Force -Path $StagingDist | Out-Null

$RepoDist = Join-Path $Root "dist"
$RepoBuild = Join-Path $Root "build"
if (Test-Path $RepoDist) { Remove-Item -Recurse -Force $RepoDist }
if (Test-Path $RepoBuild) { Remove-Item -Recurse -Force $RepoBuild }

Write-Host "Running PyInstaller (one-folder, no UPX, windowed, staging outside OneDrive)..."
& $Python -m PyInstaller --noconfirm --clean --distpath $StagingDist --workpath $StagingWork (Join-Path $Root "packaging\leadfinder.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$StagedApp = Join-Path $StagingDist "LeadFinder"
$Exe = Join-Path $StagedApp "LeadFinder.exe"
if (-not (Test-Path $Exe)) { throw "LeadFinder.exe was not produced." }

Copy-Item (Join-Path $Root "LICENSE") (Join-Path $StagedApp "LICENSE") -Force
Copy-Item (Join-Path $Root "README.md") (Join-Path $StagedApp "README.md") -Force

$ReleaseDir = Join-Path $Root "dist\release"
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
$LeaksReport = Join-Path $ReleaseDir "source-path-leak-notes.txt"

Write-Host "Secret scan (heuristic, not a guarantee)..."
& $Python packaging/scan_artifact.py --root $StagedApp --leaks-report $LeaksReport
if ($LASTEXITCODE -ne 0) { throw "Artifact secret scan failed." }

$env:LEADFINDER_SMOKE_EXIT = "1"
$env:LEADFINDER_IGNORE_DOTENV = "1"
$env:QT_QPA_PLATFORM = "offscreen"
Write-Host "Packaged GUI smoke (LEADFINDER_SMOKE_EXIT=1) with lock retry..."
$script:PackagedSmokeLockRetries = 0
$smokeCode = $null
$StagedWorkDir = $StagedApp
for ($i = 1; $i -le 3; $i++) {
    try {
        Write-Host "smoke attempt $i"
        $p = Start-Process -FilePath $Exe -WorkingDirectory $StagedWorkDir -Wait -PassThru -WindowStyle Hidden
        $smokeCode = $p.ExitCode
        break
    } catch {
        $text = $_.Exception.Message
        Write-Warning $text
        if (-not (Test-TransientLockMessage $text)) { throw }
        $script:PackagedSmokeLockRetries++
        if ($i -eq 3) { throw }
        Start-Sleep -Seconds (2 * $i)
    }
}
Remove-Item Env:LEADFINDER_SMOKE_EXIT -ErrorAction SilentlyContinue
if ($smokeCode -ne 0) {
    throw "PACKAGED_STARTUP failed: smoke exit $smokeCode"
}
Write-Host "PACKAGED_STARTUP PASS (lock retries used: $script:PackagedSmokeLockRetries)"

$QaRoot = Join-Path $env:TEMP "leadfinder-packaged-qa"
if (Test-Path $QaRoot) { Remove-Item -Recurse -Force $QaRoot }
New-Item -ItemType Directory -Force -Path $QaRoot | Out-Null
$env:LEADFINDER_DATA_DIR = $QaRoot
$env:LEADFINDER_IGNORE_DOTENV = "1"
$env:QT_QPA_PLATFORM = "offscreen"

function Invoke-PackagedQa([string]$Name, [hashtable]$ExtraEnv) {
    $report = Join-Path $QaRoot "$Name.json"
    $saved = @{}
    foreach ($key in @("LEADFINDER_PACKAGED_TEST", "LEADFINDER_PACKAGED_REPORT", "LEADFINDER_KEYRING_ACCOUNT_PLACES", "GOOGLE_MAPS_API_KEY", "GOOGLE_PLACES_API_KEY", "GROQ_API_KEY", "LEADFINDER_TEST_PLACES_API_KEY", "LEADFINDER_TEST_GROQ_API_KEY")) {
        $saved[$key] = [Environment]::GetEnvironmentVariable($key, "Process")
        Remove-Item "Env:$key" -ErrorAction SilentlyContinue
    }
    $env:LEADFINDER_PACKAGED_TEST = $Name
    $env:LEADFINDER_PACKAGED_REPORT = $report
    if ($ExtraEnv) {
        foreach ($pair in $ExtraEnv.GetEnumerator()) {
            Set-Item -Path "Env:$($pair.Key)" -Value $pair.Value
        }
    }
    $code = 1
    try {
        $p = Start-Process -FilePath $Exe -WorkingDirectory $StagedApp -Wait -PassThru -WindowStyle Hidden
        $code = $p.ExitCode
    } finally {
        foreach ($key in $saved.Keys) {
            $val = $saved[$key]
            if ($null -eq $val -or $val -eq "") {
                Remove-Item "Env:$key" -ErrorAction SilentlyContinue
            } else {
                Set-Item -Path "Env:$key" -Value $val
            }
        }
    }
    $status = "FAIL"
    if ($code -eq 0 -and (Test-Path $report)) { $status = "PASS" }
    Write-Host "PACKAGED_$($Name.ToUpper()) $status exit=$code report=$report"
    return @{ Name = $Name; Code = $code; Report = $report; Status = $status }
}

$qaResults = New-Object System.Collections.Generic.List[object]
if (-not $SkipPackagedQa) {
    $qaResults.Add((Invoke-PackagedQa "sqlite" @{}))
    $qaResults.Add((Invoke-PackagedQa "demo" @{}))
    $qaResults.Add((Invoke-PackagedQa "keyring" @{ LEADFINDER_KEYRING_ACCOUNT_PLACES = "google-places-api-packaged-qa" }))
    $qaResults.Add((Invoke-PackagedQa "env_precedence" @{ GOOGLE_MAPS_API_KEY = "packaged-env-dummy-not-real" }))
    $qaResults.Add((Invoke-PackagedQa "backup" @{}))
    $qaResults.Add((Invoke-PackagedQa "workspace" @{}))
    $qaResults.Add((Invoke-PackagedQa "zoneinfo" @{}))
    $qaResults.Add((Invoke-PackagedQa "diagnostics" @{}))
    $qaResults.Add((Invoke-PackagedQa "settings" @{}))
}

Remove-Item Env:LEADFINDER_DATA_DIR -ErrorAction SilentlyContinue
Remove-Item Env:LEADFINDER_PACKAGED_TEST -ErrorAction SilentlyContinue
Remove-Item Env:LEADFINDER_PACKAGED_REPORT -ErrorAction SilentlyContinue
Remove-Item Env:LEADFINDER_KEYRING_ACCOUNT_PLACES -ErrorAction SilentlyContinue
Remove-Item Env:GOOGLE_MAPS_API_KEY -ErrorAction SilentlyContinue

$RepoApp = Join-Path $Root "dist\LeadFinder"
New-Item -ItemType Directory -Force -Path (Join-Path $Root "dist") | Out-Null
Copy-Item -Recurse -Force $StagedApp $RepoApp

$Version = & $Python -c "from leadfinder import __version__; print(__version__)"
$ZipName = "LeadFinder-$Version-win64-standalone.zip"
$ZipPath = Join-Path $ReleaseDir $ZipName
if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
Compress-Archive -Path $RepoApp -DestinationPath $ZipPath

$InstallerOut = $null
$InstallerTool = "not_available"
if (-not $SkipInstaller -and $Iscc) {
    $Iss = Join-Path $Root "packaging\installer\LeadFinder.iss"
    Write-Host "Building Inno Setup installer..."
    & $Iscc "/DAppVersion=$Version" "/DSourceDir=$RepoApp" "/DOutputDir=$ReleaseDir" $Iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed." }
    $InstallerOut = Join-Path $ReleaseDir "LeadFinder-Setup-$Version.exe"
    if (-not (Test-Path $InstallerOut)) { throw "Installer output missing: $InstallerOut" }
    $InstallerTool = "Inno Setup 6"
} elseif (-not $SkipInstaller) {
    Write-Host "Installer build skipped: Inno Setup 6 not found"
    Write-Host "Install Inno Setup 6 from https://jrsoftware.org/isinfo.php then re-run .\packaging\build_windows.ps1"
    Write-Host "Looked in PATH, '$env:ProgramFiles\Inno Setup 6\ISCC.exe', and '${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe'."
}

$pyinstallerVer = & $Python -c "from importlib.metadata import version; print(version('pyinstaller'))"
$pysideVer = & $Python -c "from importlib.metadata import version; print(version('PySide6-Essentials'))"
$qtVer = & $Python -c "from PySide6.QtCore import qVersion; print(qVersion())"
$pyFull = & $Python -c "import sys; print(sys.version.split()[0])"
$installerArg = @()
if ($InstallerOut) { $installerArg = @("--installer", $InstallerOut) }

& $Python packaging/write_release_manifest.py --version $Version --app-dir $RepoApp --zip $ZipPath @installerArg --release-dir $ReleaseDir --python-version $pyFull --pyinstaller-version $pyinstallerVer --pyside-version $pysideVer --qt-version $qtVer --installer-tool $InstallerTool
if ($LASTEXITCODE -ne 0) { throw "Release manifest failed." }

$failedQa = @($qaResults | Where-Object { $_.Status -ne "PASS" })
if ($failedQa.Count -gt 0) {
    $names = ($failedQa | ForEach-Object { $_.Name }) -join ", "
    throw "Packaged QA failed: $names"
}

if ($InstallerOut -and (Test-Path $InstallerOut) -and -not $SkipInstaller) {
    $installerSmoke = Join-Path $Root "packaging\smoke_installer.ps1"
    Write-Host "Running installer smoke..."
    & $installerSmoke -SetupExe $InstallerOut
    if ($LASTEXITCODE -ne 0) { throw "Installer smoke failed." }
}

Write-Host "Build complete."
Write-Host "App folder: $RepoApp"
Write-Host "Release dir: $ReleaseDir"
Write-Host "Standalone ZIP: $ZipPath"
if ($InstallerOut -and (Test-Path $InstallerOut)) {
    Write-Host "Installer: $InstallerOut"
} else {
    Write-Host "INSTALLER_BUILD NOT_AVAILABLE"
}
