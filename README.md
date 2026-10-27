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
3. If multiple companies are loaded and Tally XML cannot uniquely identify the active company, enable ODBC verification in the backend configuration.
4. Keep Tally open while refreshing vouchers or generating documents.

The XML interface is required for voucher data. Optional ODBC configuration is only used to verify the active company.

## Local development

### Backend

```powershell
cd D:\langhar\backend
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend

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
```

The company document profile is configured in `backend/config/company_profile.json`; Python defaults are defined in `backend/src/utils/company_helper.py`. Tally remains the source of voucher data.

## Docker

The Docker Compose setup builds the Angular frontend and FastAPI backend into one local service, normally available at `http://localhost:8000`.

```powershell
.\run-docker.bat
```

Or:

```powershell
docker compose up -d --build
```

When Tally runs on the Windows host, configure the container's Tally host as `http://host.docker.internal` so the container can reach port `9000`.

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
