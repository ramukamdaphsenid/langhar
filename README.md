# Langhar — Enterprise Rice Platform & Tally Prime Sync Hub

An enterprise-grade platform for **Rice Mills, Grain Processors & Agro Commodities**, integrating **Tally Prime** ERP (via HTTP XML Server or ODBC) with **Google Firebase Cloud Firestore** and modular business operations.

---

## 🚀 Key Features

- **Native Tally Prime HTTP XML API**: Communicates directly with Tally Prime's built-in XML server on port 9000 without requiring 32-bit/64-bit ODBC driver configurations.
- **True Incremental Synchronization**: Leverages Tally's internal `$AlterID` sequence counter to only fetch new and modified vouchers since the last sync cycle.
- **Deep Hierarchical Extraction**: Captures header details, party GSTIN/state, inventory line items (quantities, rates, units, batches), and ledger entries (CGST, SGST, IGST, Round Off, Delivery charges).
- **Idempotent Upserts**: Uses sanitized Tally `GUID` as the Firestore Document ID with `merge=True`, avoiding duplicates and preserving custom Firestore fields.
- **Multiple Execution Modes**:
  - **On-demand CLI**: Manual runs or via Windows Task Scheduler.
  - **Date Range Sync**: Backfill or audit historical periods (`--from-date` / `--to-date`).
  - **Automated Daemon**: Runs continuously in the background at configurable intervals.
- **Full ODBC Support (Optional)**: Includes a ready-to-use ODBC client if your organization prefers Windows DSN connectivity.

---

## 🔍 How Tally Prime Exposes Data & How Vouchers Are Read

### 1. Enabling Tally Prime Server Mode
By default, Tally Prime has its local XML/ODBC server disabled. To enable it:
1. Open Tally Prime.
2. Press **`F1` (Help)** -> **Settings** -> **Connectivity**.
3. Configure the following:
   - **TallyPrime acts as**: `Both` or `Server`
   - **Enable ODBC**: `Yes`
   - **Port**: `9000` (default)
4. Restart Tally Prime.
5. Test connectivity: Open `http://localhost:9000` in any web browser. Tally will return:
   ```xml
   <RESPONSE>Tally Server is Running</RESPONSE>
   ```

### 2. Identifying & Querying Sales Vouchers via XML/TDL
When querying Tally, the sync engine sends an HTTP `POST` request with a **TDL (Tally Definition Language)** XML payload:
- **Sales Voucher Filter**: Uses `$$IsSales:$VoucherTypeName` to capture standard sales invoices as well as custom sales types (e.g., *Tax Invoice*, *Export Sales*, *Cash Sales*).
- **Incremental Filter**: Uses `$AlterID > [LAST_ALTER_ID]`. Every time a voucher is created or edited in Tally, Tally increments its internal `AlterID`.
- **Field Fetching**: Uses `<FETCH>` to extract:
  - `GUID`, `ALTERID`, `MASTERID`, `VOUCHERNUMBER`, `DATE`
  - `PARTYLEDGERNAME`, `PARTYNAME`, `STATENAME`, `PARTYGSTIN`, `PLACEOFSUPPLY`
  - `ALLLEDGERENTRIES.LIST` (Ledger breakdown: Sales, CGST, SGST, IGST, etc.)
  - `ALLINVENTORYENTRIES.LIST` (Stock item names, billed quantities, rates, amounts, batch allocations)

---

## 📦 Project Structure

```
d:/langhar/
├── config/
│   ├── __init__.py
│   └── settings.py               # Pydantic environment configurations
├── src/
│   ├── tally/
│   │   ├── client.py             # Tally XML HTTP client (POST to :9000)
│   │   ├── queries.py            # TDL XML request generator
│   │   ├── parser.py             # Robust XML to Python dict converter
│   │   └── odbc_client.py        # Optional Windows ODBC client
│   ├── firebase/
│   │   └── client.py             # Firestore client with batch writes
│   ├── sync/
│   │   ├── engine.py             # Sync coordinator
│   │   └── state.py              # Local .sync_state.json manager
│   └── utils/
│       └── logger.py             # Rich console formatting
├── tests/
│   ├── mock_sales_vouchers.xml   # Realistic sample Tally XML
│   └── test_sync.py              # Automated test suite
├── .env.example                  # Environment configuration template
├── requirements.txt              # Python dependencies
├── main.py                       # CLI interface
└── README.md                     # Documentation
```

---

## 🛠️ Installation & Setup

### 1. Prerequisites
- **Windows OS** with **Python 3.10+** (Python 3.12 verified).
- **Tally Prime** running on the machine or local network.
- A **Firebase Project** with Cloud Firestore enabled.

### 2. Setup Virtual Environment
The virtual environment has already been created in this project:
```powershell
# Activate the virtual environment
.\venv\Scripts\Activate.ps1

# (Optional) Reinstall dependencies if needed
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
copy .env.example .env
```
Edit `.env` with your settings:
```ini
TALLY_HOST=http://localhost
TALLY_PORT=9000
TALLY_COMPANY=               # Optional: Leave blank to use active company in Tally

FIREBASE_CREDENTIALS_PATH=serviceAccountKey.json
FIREBASE_COLLECTION_NAME=sales_vouchers

SYNC_INTERVAL_SECONDS=120
BATCH_SIZE=100
```

### 4. Configure Firebase Service Account
1. Open the [Firebase Console](https://console.firebase.google.com).
2. Go to **Project Settings** (gear icon) -> **Service Accounts**.
3. Click **Generate New Private Key** and download the JSON file.
4. Rename and save this file as:
   ```
   d:\langhar\serviceAccountKey.json
   ```

---

## ⚡ Usage & CLI Commands

### 1. Verify Connectivity
Run the built-in diagnostic tool to test connections to both Tally Prime and Firebase:
```powershell
.\venv\Scripts\python main.py check
```

### 2. Run Incremental Sync
Syncs only vouchers added or modified since the last run:
```powershell
.\venv\Scripts\python main.py sync
```

### 3. Run Date-Filtered Sync
Sync vouchers within a specific date range:
```powershell
.\venv\Scripts\python main.py sync --from-date 2024-04-01 --to-date 2024-04-30
```

### 4. Force Full Re-sync
Disregards the last synced Alter ID and checks all vouchers:
```powershell
.\venv\Scripts\python main.py sync --full
```

### 5. Continuous Daemon Mode
Runs the sync engine continuously in the background on an automated schedule:
```powershell
.\venv\Scripts\python main.py daemon --interval 60
```

### 6. View Sync State & Statistics
Displays the last sync timestamp, highest Alter ID synced, and total counts:
```powershell
.\venv\Scripts\python main.py status
```

### 7. Reset Sync State
Resets the local `.sync_state.json` file back to 0:
```powershell
.\venv\Scripts\python main.py reset-state
```

### 8. Export Sample Data
Generates a `sample_vouchers.json` file from live Tally (or offline mock data) so you can inspect the exact Firestore document structure:
```powershell
.\venv\Scripts\python main.py export-sample
```

---

## 📄 Firestore Document Schema

Each sales voucher is stored in Firestore with the document ID: `tally_{GUID}`:

```json
{
  "doc_id": "tally_d3b1e56b_4b53_4dc9_b14e_4e6fefc45d3e_00000001",
  "guid": "d3b1e56b-4b53-4dc9-b14e-4e6fefc45d3e-00000001",
  "alter_id": 10045,
  "master_id": 5001,
  "voucher_number": "INV-2024-001",
  "voucher_type": "Sales",
  "date": "2024-04-15",
  "effective_date": "2024-04-15",
  "party": {
    "ledger_name": "Acme Industrial Solutions",
    "name": "Acme Industrial Solutions Pvt Ltd",
    "state": "Maharashtra",
    "place_of_supply": "Maharashtra",
    "gstin": "27AABCA1234F1Z5",
    "gst_registration_type": "Regular"
  },
  "total_amount": 11800.0,
  "narration": "Supply of industrial electrical equipment against PO-889",
  "reference": "PO-889",
  "items": [
    {
      "item_name": "Heavy Duty Circuit Breaker 32A",
      "billed_qty": "10 Nos",
      "quantity": 10.0,
      "rate": 1000.0,
      "rate_raw": "1000.00/Nos",
      "amount": 10000.0,
      "discount": 0.0,
      "batches": [
        {
          "batch_name": "BATCH-APR-24",
          "godown_name": "Main Warehouse",
          "amount": 10000.0,
          "billed_qty": "10 Nos"
        }
      ]
    }
  ],
  "ledger_entries": [
    {
      "ledger_name": "Acme Industrial Solutions",
      "amount": 11800.0,
      "raw_amount": -11800.0,
      "is_deemed_positive": true
    },
    {
      "ledger_name": "Sales Account",
      "amount": 10000.0,
      "raw_amount": 10000.0,
      "is_deemed_positive": false
    },
    {
      "ledger_name": "Output CGST @ 9%",
      "amount": 900.0,
      "raw_amount": 900.0,
      "is_deemed_positive": false
    },
    {
      "ledger_name": "Output SGST @ 9%",
      "amount": 900.0,
      "raw_amount": 900.0,
      "is_deemed_positive": false
    }
  ],
  "taxes": {
    "cgst": 900.0,
    "sgst": 900.0,
    "igst": 0.0,
    "round_off": 0.0,
    "other_charges": 0.0
  },
  "source": "tally_prime",
  "synced_at": "Firestore ServerTimestamp",
  "last_updated": "2024-04-15T10:30:00Z"
}
```

---

## 🧪 Running Unit Tests

Run the test suite to verify parsing logic, calculations, and state tracking without needing a live Tally connection:
```powershell
.\venv\Scripts\python -m unittest tests/test_sync.py
```

---

## 🖥️ Angular Web Dashboard & Control Center

A modern, standalone Angular frontend is included in `frontend/`:

### Development Mode (Separate Servers)
1. **Start Backend**:
   ```powershell
   cd d:\langhar\backend
   .\venv\Scripts\python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
   ```
2. **Start Frontend**:
   ```powershell
   cd d:\langhar\frontend
   npm start
   ```
   Open `http://localhost:4200` in your browser.

---

## 🐳 Container Deployment (Docker)

Both the Angular frontend and FastAPI backend can be built into a **single unified container** that serves the full UI and REST API on **`http://localhost:8000`**.

### 1-Click Launch (Windows)
Double-click or run:
```powershell
.\run-docker.bat
```

### Or Using Docker Compose
```powershell
docker compose up -d --build
```

> **Note on Tally Connectivity**: The container uses `host.docker.internal` to communicate with Tally Prime running on the Windows host on port 9000.


