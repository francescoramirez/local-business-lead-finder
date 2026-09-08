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

Clean Windows 10 x64 qualification for this 1.3.0 train is complete:

**PASS — LEADFINDER_1_3_CLEAN_WINDOWS_DISTRIBUTION_VALIDATED**

Standalone ZIP, Setup EXE, Demo Mode, Demo Pipeline, installer install/reinstall/uninstall, and user-data preservation were verified on a machine without Python, Git, or a source checkout. See [docs/CLEAN_WINDOWS_TEST.md](CLEAN_WINDOWS_TEST.md) if you repeat the checklist.

## Screenshots

Capture real GUI screenshots from **Demo Mode** only (`docs/images/README.md`). Do not photograph live Places payloads or API keys.

## Git (owner, not the coding agent unless asked)

```text
git diff
git add …
git commit
# v1.3.0 may already exist on origin; move the tag onto this commit only if binaries match this tree
git tag -f v1.3.0
```

Do not attach release binaries until the tag commit is the tree that produced those hashes. Do not force-push `main`. Force-push **only** the `v1.3.0` tag if you intentionally replace the previous tag object.

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
