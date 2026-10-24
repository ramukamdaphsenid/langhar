# TallySync Studio — Enterprise Angular Frontend

A modern, high-performance Angular dashboard and control center for managing real-time and incremental synchronization from **Tally Prime** (via HTTP XML Server or ODBC) to **Google Firebase Cloud Firestore**.

---

## 🌟 Key Features

1. **Synchronization Command Center**:
   - **Quick Incremental Sync**: Trigger an instant pull of all vouchers created or modified since the last `$AlterID` watermark.
   - **Full Resync**: Bypass AlterID filtering to audit and re-sync all sales vouchers across the company.
   - **Date-Range Backfill**: Run targeted synchronization for specific periods with quick presets (*Today*, *Yesterday*, *Last 7 Days*, *This Month*, *Financial Year*).
   - **State Watermark Reset**: Safely reset the `.sync_state.json` AlterID tracking counter back to 0.

2. **Real-Time KPI & Status Monitoring**:
   - **Engine Status Badge**: Instant visual feedback on whether synchronization is actively executing, idle, succeeded, or failed.
   - **Watermark Counter**: Current `$AlterID` position in Tally's transactional event log.
   - **Total Synced Counter**: Running total of vouchers written to Firestore.
   - **Automated Daemon Scheduler Widget**: Start or stop background synchronization workers with custom intervals (10s, 30s, 60s, 5m, 15m) and a live countdown timer.

3. **Multi-Tab Workspace**:
   - **Voucher Explorer**: Interactive table of sales vouchers with search filtering (by Voucher Number, Party Name, GSTIN, State, GUID).
   - **Voucher Inspector Modal**: Drill into hierarchical voucher data, line item quantities, rates, batch allocations, and ledger/tax distributions (CGST, SGST, IGST, Round Off).
   - **Live Log Terminal**: Monospace streaming terminal showing backend execution logs with level filters (`ALL`, `INFO`, `WARNING`, `ERROR`), search, and clipboard copy.
   - **System Diagnostics**: Live connection health check for Tally Prime (port 9000 XML) and Firebase Firestore with step-by-step troubleshooting guides.

---

## 🚀 Quick Start

### 1. Start the FastAPI Backend
In the `backend` folder:
```powershell
cd d:\langhar\backend
.\venv\Scripts\Activate.ps1
python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Start the Angular Frontend
In the `frontend` folder:
```powershell
cd d:\langhar\frontend
npm start
```
The application will launch on **`http://localhost:4200`** with dev server proxy to `http://127.0.0.1:8000`.

### 3. Production Build
```powershell
npm run build
```
Build output is saved to `dist/frontend`.
