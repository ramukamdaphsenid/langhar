export interface SyncState {
  last_alter_id: number;
  last_sync_timestamp: string | null;
  total_vouchers_synced: number;
  last_status: 'SUCCESS' | 'FAILED' | 'RUNNING' | 'NEVER_RUN' | string;
  last_error: string | null;
  synced_company_name?: string | null;
  state_file: string;
}

export interface DaemonInfo {
  is_running: boolean;
  interval_seconds: number;
  last_run: string | null;
  next_countdown_seconds: number | null;
}

export interface SyncConfig {
  tally_url: string;
  tally_target: string;
  tally_company: string;
  target_company?: string;
  active_tally_company?: string | null;
  company_match_ok?: boolean | null;
  company_match_message?: string | null;
  tally_use_odbc: boolean;
  firebase_collection: string;
  credentials_path: string;
  credentials_exists: boolean;
}

export interface SyncResult {
  status: 'SUCCESS' | 'FAILED' | 'PARTIAL' | string;
  synced_count: number;
  from_date?: string | null;
  to_date?: string | null;
  last_alter_id?: number;
  elapsed_seconds?: number;
  error?: string | null;
  message?: string;
}

export interface SyncStatusResponse {
  is_syncing: boolean;
  state: SyncState;
  daemon: DaemonInfo;
  last_sync_result: SyncResult | null;
  config: SyncConfig;
}

export interface ServiceHealth {
  ok: boolean;
  message: string;
  target: string;
  instructions?: string | null;
  credentials_found?: boolean;
}

export interface DiagnosticsResponse {
  timestamp: string;
  tally: ServiceHealth;
  firebase: ServiceHealth;
}

export interface SyncRequestPayload {
  from_date?: string;
  to_date?: string;
  full?: boolean;
}

export interface BatchItem {
  batch_name?: string;
  godown_name?: string;
  amount?: number;
  billed_qty?: string;
}

export interface InventoryItem {
  item_name: string;
  billed_qty?: string;
  quantity?: number;
  rate?: number | string;
  rate_raw?: string;
  amount?: number;
  unit?: string;
  discount?: number;
  batch_name?: string;
  batches?: BatchItem[];
}

export interface LedgerItem {
  ledger_name: string;
  amount: number | string;
  raw_amount?: number | string;
  is_deemed_positive?: boolean;
}

export interface VoucherParty {
  name?: string;
  ledger_name?: string;
  state?: string;
  place_of_supply?: string;
  gstin?: string;
  gst_registration_type?: string;
}

export interface VoucherItem {
  doc_id?: string;
  guid: string;
  alter_id?: number;
  master_id?: number;
  voucher_number: string;
  company_name?: string;
  date: string;
  effective_date?: string;
  voucher_type?: string;
  vehicle_number?: string;
  party_name?: string;
  party_ledger_name?: string;
  party_gstin?: string;
  state_name?: string;
  place_of_supply?: string;
  party?: VoucherParty;
  items?: InventoryItem[];
  inventory_entries?: InventoryItem[];
  ledger_entries?: LedgerItem[];
  taxes?: {
    cgst?: number;
    sgst?: number;
    igst?: number;
    round_off?: number;
    other_charges?: number;
  };
  total_amount?: number;
  narration?: string;
  reference?: string;
  source?: string;
  synced_at?: string;
}

export interface VouchersResponse {
  source: 'live' | 'firestore' | 'mock';
  total: number;
  returned: number;
  vouchers: VoucherItem[];
}
