# Desktop build

LeadFinder 1.3 ships as a **Windows x64 one-folder** application built with **PyInstaller**, plus an optional **Inno Setup** per-user installer.

Source Python remains cross-platform (**3.10+**). The **official packager** for Windows release artifacts is **Python 3.12 x64**. Do not raise `requires-python` only to match the packager.

## Why PyInstaller, one-folder, no UPX

| Option | Verdict |
| --- | --- |
| PyInstaller | Chosen. Mature PySide6 hooks, one-folder Qt plugin layout, straightforward CI, debuggable. |
| Nuitka | Not used. Longer compiles, heavier Qt plugin maintenance, weaker fit for a first desktop pipeline. |

**One-folder** (`dist/LeadFinder/LeadFinder.exe` + `_internal/`) is the primary layout. Qt platform plugins, image formats, and styles stay on disk instead of extracting from a one-file archive on every launch.

**UPX is off.** Compression increases Windows Defender false-positive risk and does not help Qt much.

`gui` extra pins `PySide6-Essentials>=6.6,<7`. `build` extra pins `pyinstaller>=6.10,<7`. `tzdata` is included so packaged Windows can resolve IANA zones used by analytics.

## Prerequisites (maintainer machine)

- Windows 10/11 x64
- **Python 3.12 x64** (source still works on 3.10+)
- Optional: [Inno Setup 6](https://jrsoftware.org/isinfo.php) for the installer (`ISCC.exe` on PATH or under `C:\Program Files (x86)\Inno Setup 6\` / `C:\Program Files\Inno Setup 6\`)

Do not rely on an ambiguous global `python` if it is 3.14 or another version. `packaging/build_windows.ps1` looks for 3.12 (`py -3.12`, `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`, or `LEADFINDER_PYTHON`) and builds inside `%TEMP%\leadfinder-official-venv-3.12`.

PyInstaller work/dist staging uses `%TEMP%\leadfinder-build` so OneDrive file locks on the repo `dist/` folder are less likely. Final files are copied to `dist/LeadFinder` and `dist/release/`.

## Local Windows build

```powershell
.\packaging\build_windows.ps1
.\packaging\build_windows.ps1 -SkipTests    # dev iteration only
.\packaging\validate_release.ps1
```

The script:

1. Resolves Python 3.12 x64 and prints Python / pip / PyInstaller / PySide6 / Qt / Windows / Inno
2. Installs `.[gui,build,dev]` into the isolated venv
3. Runs ruff, pytest, mypy, compileall unless `-SkipTests`
4. Builds one-folder, UPX off
5. Heuristic-scans the artifact (not a security proof)
6. Packaged GUI smoke (`LEADFINDER_SMOKE_EXIT=1`) with up to 3 attempts **only** for sharing-violation / access-denied style locks
7. Packaged QA hooks (sqlite, demo, keyring on a **QA account name**, env precedence, backup, workspace, zoneinfo, diagnostics, settings imports)
8. Zips standalone folder, compiles Inno if present, writes `dist/release/SHA256SUMS.txt` and `release-manifest.json`

This is a **repeatable build process**, not bit-for-bit identical binaries.

If Inno Setup is missing, the script prints `Installer build skipped: Inno Setup 6 not found` and does **not** auto-install Inno. No fake setup EXE is created.

## Artifacts

```text
dist/LeadFinder/                                 one-folder app
dist/release/LeadFinder-1.3.0-win64-standalone.zip
dist/release/LeadFinder-Setup-1.3.0.exe          only if ISCC exists
dist/release/SHA256SUMS.txt
dist/release/release-manifest.json
```

“Standalone ZIP” means the binaries do not need a Python install. **User data still lives in OS app-data**, not next to the EXE.

## Installer

- Technology: Inno Setup 6
- Scope: **per-user** (`PrivilegesRequired=lowest`)
- Default directory: `%LOCALAPPDATA%\Programs\LeadFinder`
- AppId (stable across versions): `{7C3E9B1A-4F2D-4A8E-9C11-A1B2C3D4E5F6}`
- Publisher: `FrancescoRamirezC` (same as pyproject authors)
- Shortcuts: Start Menu; optional Desktop; **WorkingDir = {app}** (never the git checkout)
- Launch after install: yes (skipped in silent mode)
- Uninstall: program files and shortcuts only. No `[UninstallDelete]` rules for `%LOCALAPPDATA%\LeadFinder\LeadFinder\`

## Code signing and SmartScreen

Builds are **unsigned**. SmartScreen may warn for unsigned builds. There is no certificate in this repository. Do not self-sign and call it trust. Do not disable Windows Defender.

## Antivirus

False positives are possible for PyInstaller binaries. Do not use UPX. Report hashes from `SHA256SUMS.txt` with any vendor submission.

## Clean-machine checklist

Follow [docs/CLEAN_WINDOWS_TEST.md](CLEAN_WINDOWS_TEST.md) on Windows 10/11 x64 **without** Python, Git, or the source repo.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| App does not start | `%LOCALAPPDATA%\LeadFinder\LeadFinder\Logs\leadfinder.log` |
| Qt platform plugin error | Rebuild; do not delete `_internal` |
| “Couldn’t open your workspace” | File → Restore, or Demo Mode. Do not delete the DB blindly |
| SmartScreen | Expected for unsigned builds |
| API key | Settings → API, or environment variables. Never `.env` next to the installed EXE |
| Sharing violation after PyInstaller | Staging dir is `%TEMP%\leadfinder-build`; smoke retries lock errors only |

## Smoke / QA hooks (not user-facing)

```text
LEADFINDER_SMOKE_EXIT=1
LEADFINDER_DATA_DIR=<temp>
LEADFINDER_PACKAGED_TEST=sqlite
LEADFINDER_PACKAGED_REPORT=<json>
LEADFINDER_KEYRING_ACCOUNT_PLACES=google-places-api-packaged-qa
LEADFINDER_IGNORE_DOTENV=1
```

Smoke initializes Qt, opens a temporary SQLite file (not the user database), constructs the main window, and exits. Packaged tests must set `LEADFINDER_DATA_DIR` so owner app-data is not used. Keyring QA must set `LEADFINDER_KEYRING_ACCOUNT_PLACES` so the production credential account is not overwritten.

## Skipped in 1.3

- Single-instance lock (SQLite WAL + busy timeout remains; two GUIs on one DB are unsupported)
- File associations
- Auto-update / phone-home
- Authenticode signing
- Last-crash telemetry prompt
