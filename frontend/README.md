# Langhar frontend

Angular frontend for live Tally voucher review, company document information, and invoice/delivery-note PDF generation.

## Screens

- **Vouchers** (`/vouchers`): reads the active company's vouchers directly from the backend/Tally connection. Search and date filters operate on the loaded live response. Each voucher can be opened for details and used to create an invoice or delivery-note PDF.
- **Company information** (`/company`): edits the business details printed on generated PDFs.

## Run locally

Start the FastAPI backend on `http://127.0.0.1:8000`, then run:

```powershell
npm install
npm start
```

Open `http://localhost:4200`. The dev-server proxy forwards `/api` calls to the backend.

## Build

```powershell
npm run build
```

The production output is written to `dist/frontend`.
