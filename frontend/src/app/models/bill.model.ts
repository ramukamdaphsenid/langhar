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
  voucherType?: string;
  dateISO: string;
  partyName: string;
  partyState?: string;
  partyGstin?: string;
  narration?: string;
  truckNumber?: string;
  items: SaleItem[];
  totalAmount: number;
  totalGst?: number;
}
