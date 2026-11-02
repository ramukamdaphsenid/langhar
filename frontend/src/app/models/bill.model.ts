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
  /** Reference field from Tally - often contains delivery note number */
  reference?: string;
  /** Original voucher/invoice number from Tally */
  invoiceNumber?: string;
}
