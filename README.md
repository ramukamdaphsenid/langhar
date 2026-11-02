# Langhar Tally Vouchers

Langhar is a local app for reading sales vouchers from the company currently open in Tally Prime and generating invoice and delivery-note PDFs.

## What the app includes

- **Vouchers** (`/vouchers`): loads vouchers directly from Tally, with search, date filters, voucher details, and PDF actions.
- **Company document profile**: reads the configured business details used on generated documents.
- **Documents**: create or download an invoice or delivery note PDF from a selected voucher.

Voucher data shown in the app is requested live from Tally and is not cached locally. Document details are read from `backend/config/company_profile.json` when its company name matches the active Tally company; otherwise, Python defaults are used.

## Tally setup

1. Start Tally Prime and open the company whose vouchers you need.
2. Enable the Tally XML HTTP server in **F1 (Help) → Settings → Connectivity**. Use port `9000` unless configured otherwise.
3. If multiple companies are loaded and Tally XML cannot uniquely identify the active company, enable ODBC verification in the backend configuration. The backend includes `pyodbc`; configure the Tally ODBC DSN on the machine running Langhar.
4. Keep Tally open while refreshing vouchers or generating documents.

The XML interface is required for voucher data. Optional ODBC configuration is only used to verify the active company.

## Local development

### macOS

Run `start-local.command` from Finder or the terminal. It offers to install missing Python or Node.js runtimes and prepares backend and frontend dependencies on first run. The Angular frontend requires Node.js `22.22.3+`, `24.15.0+`, or `26+`; the launcher offers a Homebrew upgrade if the installed version is too old. It opens `http://localhost:4200` only after both services are ready; press Control-C in its Terminal window to stop them.

```bash
python3 -m venv backend/venv
backend/venv/bin/python -m pip install -r backend/requirements.txt
npm --prefix frontend install
./start-local.command
```

### Windows

#### Backend

```powershell
cd D:\langhar\backend
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
```

#### Frontend

```powershell
cd D:\langhar\frontend
npm install
npm start
```

Open `http://localhost:4200`. The Angular development server proxies `/api` requests to the local backend.

## Configuration and storage

Backend configuration is read from `backend/.env` (copy `backend/.env.example` to get started). The main settings are:

```ini
TALLY_HOST=http://localhost
TALLY_PORT=9000
TALLY_TIMEOUT=30
TALLY_USE_ODBC=false
TALLY_ODBC_DSN=TallyODBC64_9000
APP_HOST=127.0.0.1
APP_PORT=8000
```

`APP_HOST` and `APP_PORT` control the local web server used by the packaged app. If the port is busy, the next free port is used automatically.

The company document profile is configured in `backend/config/company_profile.json`; Python defaults are defined in `backend/src/utils/company_helper.py`. Tally remains the source of voucher data.

## Windows installer

To build a shareable Windows installer, use a 64-bit Windows machine with Python 3.12, Node.js 22.22.3+ (or 24.15.0+ / 26+), and Inno Setup 6 installed. Run:

```powershell
.\build-windows-installer.bat
```

The installer is written to `dist\installer\Langhar-Setup.exe`. Recipients do not need Python or Node.js. They do need Tally Prime installed and running with its XML HTTP server enabled on port `9000`, and the Microsoft Edge WebView2 Runtime installed. Launching Langhar opens the app in its own window without a separate console; closing the app window stops the local service. Startup errors are shown in a dialog and logged to `%LOCALAPPDATA%\Langhar\logs\langhar.log`.

Installer configuration and the editable company document profile are stored per user under `%LOCALAPPDATA%\Langhar`. Set `TALLY_HOST`, `TALLY_PORT`, `APP_PORT`, and other backend options in `%LOCALAPPDATA%\Langhar\.env` if the defaults do not match the recipient's setup. Changing the port never requires rebuilding the app.

The installer includes the repository's configured company profile and company defaults. Review those details before sharing the installer.

For build internals, the change-to-rebuild checklist, port configuration, and troubleshooting, see [`packaging/windows/README.md`](packaging/windows/README.md).

## Tests

```powershell
cd D:\langhar\backend
python -m unittest tests.test_tally
```

Build the frontend with:

```powershell
cd D:\langhar\frontend
npm run build
```
