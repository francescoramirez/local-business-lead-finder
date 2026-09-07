Windows packaging lives in this folder. Maintainer instructions: [docs/DESKTOP_BUILD.md](../docs/DESKTOP_BUILD.md). Clean-machine steps: [docs/CLEAN_WINDOWS_TEST.md](../docs/CLEAN_WINDOWS_TEST.md).

Official packager: Python 3.12 x64 via `.\packaging\build_windows.ps1`.

```text
packaging/leadfinder.spec
packaging/build_windows.ps1
packaging/validate_release.ps1
packaging/smoke_installer.ps1
packaging/installer/LeadFinder.iss
```

Do not commit `dist/`, `build/`, or `file_version_info.txt`.
