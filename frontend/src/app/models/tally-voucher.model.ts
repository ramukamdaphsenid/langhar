export interface ActiveCompany {
  company_id: string;
  company_name: string;
}

export interface ActiveCompanyResponse {
  active_company: ActiveCompany | null;
  tally_online: boolean;
}

export interface BatchItem {
  batch_name?: string;
  godown_name?: string;
  amount?: number;
  billed_qty?: string;
  quantity?: number;
  unit?: string;
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
  voucher_number: string;
  date: string;
  voucher_type?: string;
  vehicle_number?: string;
  party?: VoucherParty;
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
}

export interface VouchersResponse {
  source: 'live';
  total: number;
  vouchers: VoucherItem[];
}
