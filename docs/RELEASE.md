# Release checklist

Owner steps for publishing LeadFinder. This file does not publish anything by itself.

Current product version is taken from `leadfinder.__version__` / `pyproject.toml` (**1.3.0** for this train). Do not bump the version as part of packaging qualification.

## Build

Official packager: **Python 3.12 x64**.

```powershell
.\packaging\build_windows.ps1
.\packaging\validate_release.ps1
```

Expect `dist/release/` to contain the standalone ZIP, `SHA256SUMS.txt`, `release-manifest.json`, and `LeadFinder-Setup-1.3.0.exe` when Inno Setup 6 is installed. Hashes must be from **this** 3.12 build, not an older 3.14 build.

## Validate (this machine)

- Source: ruff, pytest, mypy, compileall (the build script runs these unless `-SkipTests`)
- Packaged smoke `LEADFINDER_SMOKE_EXIT=1` exit 0
- Packaged QA JSON reports under `%TEMP%\leadfinder-packaged-qa\`
- Installer silent smoke (`packaging/smoke_installer.ps1`) when the setup EXE exists
- Heuristic artifact scan (not a security proof)

## Clean-machine

Run [docs/CLEAN_WINDOWS_TEST.md](CLEAN_WINDOWS_TEST.md) on Windows 10/11 x64 with no Python, Git, or source checkout. Until that is done, `CLEAN_WINDOWS_NO_PYTHON` stays **MANUAL_REQUIRED**.

## Screenshots

Capture real GUI screenshots from **Demo Mode** only (`docs/images/README.md`). Do not photograph live Places payloads or API keys.

## Git (owner, not the coding agent unless asked)

```text
git diff
git add …
git commit
git tag v1.3.0
```

Do not tag until clean-machine (or an explicit owner waiver) and artifact hashes are the ones you will attach.

## GitHub Release

Create a GitHub Release **manually** and attach:

- `LeadFinder-Setup-1.3.0.exe` (if built)
- `LeadFinder-1.3.0-win64-standalone.zip`
- `SHA256SUMS.txt`
- `release-manifest.json`

Release notes should say the build is **unsigned** and that SmartScreen may warn. Do not tell users to disable antivirus. Do not paste API keys.

Do not publish to PyPI unless you intend a source package release as well.

## Not automated

CI may upload a **workflow artifact** (not a GitHub Release). There is no auto-updater.
