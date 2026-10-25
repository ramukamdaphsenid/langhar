import type { VoucherItem } from './sync.models';

export interface SaleItem {
  name: string;
  quantity: number;
  rate: number;
  amount: number;
  unit?: string;
  billed_qty?: string;
}

export interface SaleRecord {
  voucherNumber: string;
  dateISO: string;
  partyName: string;
  partyAddress?: string;
  partyState?: string;
  partyGstin?: string;
  narration?: string;
  truckNumber?: string;
  deliveryNote?: string;
  items: SaleItem[];
  totalAmount: number;
  totalGst?: number;
  udfs?: Record<string, string>;
  rowId: string;
  rawVoucher?: VoucherItem;
}
