# Clean Windows machine test (LeadFinder 1.3.0)

Use a **Windows 10 or Windows 11 x64** PC (or VM) that does **not** have:

- Python
- Git
- this source repository
- Visual Studio / VS Code (optional; must not be required)

Do **not** run this checklist against the developer machine’s real workspace as a destructive experiment. Uninstall keeps `%LOCALAPPDATA%\LeadFinder\LeadFinder\` data; that is the point of steps 15–18.

Target installer: `LeadFinder-Setup-1.3.0.exe` from `dist/release/` or the GitHub Release the owner publishes.

Builds are **unsigned**. SmartScreen may warn. Do not disable Windows Defender. Do not treat a self-signed file as trusted.

## Before install

1. Copy `LeadFinder-Setup-1.3.0.exe` and `SHA256SUMS.txt` to the clean machine (USB, OneDrive download of the **release files only**, etc.).
2. Verify SHA-256. In PowerShell:

```powershell
Get-FileHash .\LeadFinder-Setup-1.3.0.exe -Algorithm SHA256
```

The hash must match the `LeadFinder-Setup-1.3.0.exe` line in `SHA256SUMS.txt`. Stop if it does not.

## Install and first run

3. Run the installer. Accept the MIT license. Default folder is `%LOCALAPPDATA%\Programs\LeadFinder`. Per-user; no admin unless the OS asks for an unrelated reason.
4. Launch **LeadFinder** from the Start Menu shortcut (optional Desktop shortcut if you selected it). Shortcut target must be `LeadFinder.exe` under that Programs folder, **not** a GitHub checkout.
5. Welcome / onboarding appears on first run.
6. Choose **Try Demo**. No Google or Groq calls. Synthetic leads only.
7. Open **Pipeline** and browse a few rows.
8. Open **Analytics** and browse. Timezone labels should not crash the UI (`America/Argentina/Buenos_Aires`, `America/New_York`, UTC are supported in code).
9. Exit the app (window close).
10. Launch LeadFinder again from Start Menu.
11. Confirm Demo data is still there (same synthetic businesses). Onboarding should not appear again.
12. Use **Return to My Workspace** (or equivalent). My Workspace starts empty on a clean machine.

## Optional credential / backup

13. Settings → API: save a **test** Places key only if you intend to. Prefer skipping live keys on a throwaway VM. Remove the key before sharing the VM image.
14. File → Backup (or equivalent). Confirm a `.db` backup appears under `%LOCALAPPDATA%\LeadFinder\LeadFinder\backups` (or the Backup folder the UI opens). Do not copy backups back onto the developer PC mixed with production data unless you mean to.

## Uninstall and data keep

15. Uninstall LeadFinder from Windows Apps & features (per-user). Confirm the dialog (if shown) that local data is **not** deleted.
16. Confirm these still exist (paths may vary slightly with Windows localization):

```text
%LOCALAPPDATA%\LeadFinder\LeadFinder\leadfinder.db
%LOCALAPPDATA%\LeadFinder\LeadFinder\leadfinder-demo.db
```

Also keep `backups\`, `exports\`, logs, and any Settings/OS credential you saved. Program files under `%LOCALAPPDATA%\Programs\LeadFinder` should be gone (or mostly gone pending reboot/locks).

## Reinstall

17. Run `LeadFinder-Setup-1.3.0.exe` again (same version is an in-place repair/upgrade; AppId is stable).
18. Launch. Demo and My Workspace databases from step 16 should open (schema migrates forward if needed). You should not need Python or Git.

## Record

Mark `CLEAN_WINDOWS_NO_PYTHON` **PASS** only after steps 1–18 on a machine that had no Python/Git/repo. Until then: **MANUAL_REQUIRED**.
