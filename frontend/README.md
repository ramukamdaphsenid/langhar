# Langhar frontend

Angular frontend for live Tally voucher review, company document information, and invoice/delivery-note PDF generation.

## Screen

- **Vouchers** (`/vouchers`): reads vouchers from the company currently open in Tally. Search and date filters operate on the loaded live response. Each voucher can be opened for details and used to create an invoice or delivery-note PDF.

Company details printed on PDFs are configured in the backend company profile, not in a frontend screen.

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
