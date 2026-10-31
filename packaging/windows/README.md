# Langhar Windows build

This document covers how the Windows executable and installer are built, what
changes require build-file edits, how to change the local port, and how to
troubleshoot a release.

## Prerequisites

Build on a 64-bit Windows machine with:

- **Python 3.12 (x64)** on `PATH`
- **Node.js 22** and `npm` on `PATH`
- **Inno Setup 6** installed (the script looks for `ISCC.exe` on `PATH`,
  `%ProgramFiles(x86)%`, `%ProgramFiles%`, and `%LOCALAPPDATA%\Programs`)

Tally Prime is only needed to *run* the app, not to build it.
The Microsoft Edge WebView2 Runtime is required to run the installed app.

## Build command

From the repository root:

```powershell
.\build-windows-installer.bat
```

Recipients of the installer do not need Python, Node.js, or any other build
tooling.

## What the script does

`build-windows-installer.bat` always performs a full build; there is no
incremental mode. It removes the previous Angular browser bundle and packaged
`dist\windows\Langhar` app before rebuilding, so stale frontend or PyInstaller
files cannot be carried into the new installer.

1. Checks that `node`, `npm`, and `python` are available.
2. Creates `.windows-build-venv` if it does not exist. This is a dedicated
   build environment, separate from `backend\venv`.
3. Installs `packaging\windows\requirements.txt`, which chains
   `backend\requirements.txt` and pins `pywebview` and `pyinstaller`.
4. Runs `npm ci` in `frontend` (wipes and reinstalls `node_modules`).
5. Runs `npm run build` to produce the production Angular bundle in
   `frontend\dist\frontend\browser`.
6. Runs PyInstaller in **onedir** mode to produce `dist\windows\Langhar`:
   - entry point: `backend\launcher.py`
   - `--paths backend` so `api`, `config`, and `src` imports resolve
   - bundles the Angular bundle as `data\static`
   - bundles `backend\config\company_profile.json` as `data`
   - collects all of `uvicorn` (it imports protocol modules dynamically)
   - collects `pywebview` and its Windows WebView2 bridge dependencies
   - Windows app and installer icons from `frontend\public\langhar-app.ico`
7. Compiles `packaging\windows\Langhar.iss` with Inno Setup, wrapping
   everything already present in `dist\windows\Langhar`.

## Outputs

| Path | Contents |
| --- | --- |
| `dist\windows\Langhar\Langhar.exe` | The application executable |
| `dist\windows\Langhar\_internal\` | Python runtime, dependencies, bundled frontend |
| `dist\installer\Langhar-Setup.exe` | The shareable per-user installer |
| `build\windows-pyinstaller\` | PyInstaller work files and the generated spec |
| `.windows-build-venv\` | Reusable build virtual environment |

`Langhar.exe` is **not** self-contained: it needs its sibling `_internal`
folder. Do not distribute the exe on its own.

## What the packaged app does at startup

`backend\launcher.py`:

1. Copies the bundled company profile to
   `%LOCALAPPDATA%\Langhar\config\company_profile.json` **only if it does not
   already exist**.
2. Picks the local port (see [Changing the port](#changing-the-port)).
3. Starts uvicorn in a supervised child process and opens the local URL in an
   embedded Edge WebView2 window.
4. Runs without a separate console window. Closing the Langhar window stops the
   service. The launcher terminates the dedicated server process and kills it
   if it does not exit promptly, so a stuck request cannot keep it running in
   the background.

Startup errors are shown in a dialog and written to
`%LOCALAPPDATA%\Langhar\logs\langhar.log`.

The WebView2 Runtime is a separate Microsoft component and is not bundled with
Langhar. Install it from Microsoft's [WebView2 download page](https://developer.microsoft.com/microsoft-edge/webview2/)
if it is not already present on the computer.

## Where the installed app stores things

| What | Location |
| --- | --- |
| Program files | `%LOCALAPPDATA%\Programs\Langhar` |
| Runtime configuration | `%LOCALAPPDATA%\Langhar\.env` |
| Company document profile | `%LOCALAPPDATA%\Langhar\config\company_profile.json` |
| Start Menu shortcut | Current user's Start Menu |

The installer uses a fixed `AppId`, so a newer `Langhar-Setup.exe` upgrades an
existing install in place. Uninstalling removes the program files but leaves
`%LOCALAPPDATA%\Langhar` (user configuration) untouched.

`backend\static` is only used when running the backend **outside** the frozen
exe (for example `python api.py`). The exe always serves the UI from its
bundled `data\static`.

## Change checklist

| Change | Action |
| --- | --- |
| Backend Python code | Rerun the build script |
| Frontend code, templates, styles | Rerun the build script |
| Files in `frontend\public` (including `langhar-app.ico`) | Rerun the build script |
| Add/remove/upgrade an API dependency | Edit `backend\requirements.txt`, rerun the build script |
| Add/remove/upgrade a Windows launcher dependency | Edit `packaging\windows\requirements.txt`, rerun the build script |
| `backend\config\company_profile.json` | Rerun the build script, but see the profile note below |
| `.env` values | No rebuild needed; edit `%LOCALAPPDATA%\Langhar\.env` on the target machine |
| Inno Setup metadata, shortcuts, install scope | Edit `packaging\windows\Langhar.iss`, then rerun the build script |
| App version | Edit `packaging\windows\Langhar.iss` (`AppVersion`) and optionally `backend\api.py` (`version=`), rerun the build script |

### Changes that need a build-file edit

- **New runtime data file** (JSON, CSV, template, font, etc.) read by the
  backend: add another `--add-data "source;destination"` argument to the
  PyInstaller command in `build-windows-installer.bat`. PyInstaller only
  collects Python modules automatically.
- **New dependency that uses dynamic imports or ships data files**: add
  `--collect-all <package>` or `--hidden-import <module>` to the same command.
  The optional ODBC verifier uses a dynamic `pyodbc` import and is included
  with `--hidden-import pyodbc`.
- **Frontend output location changes**: update the
  `--add-data "frontend\dist\frontend\browser;data\static"` path. This path is
  the Angular default because `angular.json` does not set `outputPath`.
- **Version bump**: `AppVersion` in `packaging\windows\Langhar.iss` is not
  derived from anywhere. Update it manually. The exe has no Windows version
  resource, so Explorer file properties will not show a version.

> Do **not** hand-edit `build\windows-pyinstaller\Langhar.spec`. It is
> regenerated on every build (`--noconfirm --clean`). Put changes in
> `build-windows-installer.bat` instead.

### Company profile note

The bundled profile is copied to the user's `%LOCALAPPDATA%` only when no
profile exists. If you change `backend\config\company_profile.json`, existing
installations keep their old copy after an upgrade. To pick up new values, the
user must delete `%LOCALAPPDATA%\Langhar\config\company_profile.json` (or edit
it directly) and restart Langhar.

## Changing the port

The packaged app reads its address from `%LOCALAPPDATA%\Langhar\.env`:

```ini
APP_HOST=127.0.0.1
APP_PORT=8000
```

- `APP_PORT` defaults to `8000`. If that port is busy, Langhar automatically
  checks up to 10 higher ports and records the selected port in the app log.
- `APP_HOST` defaults to `127.0.0.1`, which keeps the app local. Use `0.0.0.0`
  only if other devices on the network should connect; that exposes the app to
  the LAN.
- No rebuild or reinstall is needed to change the port, because the Angular UI
  calls the API on the same origin.
- The development scripts (`start-local.bat`, `frontend\proxy.conf.json`,
  `backend\api.py`) remain on `8000` and are not affected by `APP_PORT`.

## Troubleshooting

**The installer contains an old build.**
`Langhar.iss` only packages whatever is currently in `dist\windows\Langhar`.
Running `ISCC.exe packaging\windows\Langhar.iss` on its own will reuse stale
artifacts. Always run `build-windows-installer.bat` for a release. As a sanity
check, compare the timestamps of `dist\windows\Langhar\Langhar.exe` and
`dist\installer\Langhar-Setup.exe`.

**The installer cannot overwrite files.**
Close Langhar before running the new installer. A running exe and its
`_internal` DLLs are locked.

**The app does not open, or opens the wrong address.**
Check `%LOCALAPPDATA%\Langhar\logs\langhar.log` for startup details. If Tally
is not reachable, voucher loading fails even though the UI opens; verify
Tally's XML HTTP server (default port `9000`).

**The Download button does nothing in the installed app.**
The packaged app uses WebView2, where downloads are disabled by default. The
launcher enables pywebview's native Save As dialog for downloads. Rebuild with
`build-windows-installer.bat` and reinstall the updated installer; rebuilding
the frontend alone does not update the installed launcher.

**Port conflicts.**
Langhar falls back to the next free port (checking up to 10 higher ports) and
records the selected port in its log. If all candidate ports are busy, it
shows a startup error; free a port or set `APP_PORT` to a specific value.

**A clean rebuild is needed.**
Delete `dist\`, `build\`, `.windows-build-venv\`, `frontend\dist\`, and
`frontend\node_modules\`, then rerun the script.

**Inno Setup is not found.**
Install Inno Setup 6, or make sure `ISCC.exe` is on `PATH` or in one of the
standard install locations listed above.

**The build fails on another OS.**
PyInstaller does not cross-compile. Build on 64-bit Windows; the installer also
declares `x64os` only.
