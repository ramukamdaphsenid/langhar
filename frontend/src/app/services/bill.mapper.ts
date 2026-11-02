import type { SaleItem, SaleRecord } from '../models/bill.model';
import type { BatchItem, InventoryItem, VoucherItem } from '../models/tally-voucher.model';

export const parseCleanQuantity = (
  rawVal?: number | string,
  billedQtyStr?: string,
  batches?: BatchItem[],
  amount?: number,
  rate?: number
): { quantity: number; unit?: string } => {
  const candidates = [billedQtyStr, typeof rawVal === 'string' ? rawVal : ''];

  for (const str of candidates) {
    if (!str || typeof str !== 'string') continue;
    let s = str.trim();
    if (!s) continue;

    // Remove commas in numbers (e.g. 1,000.00 -> 1000.00) and leading '='
    s = s.replace(/,/g, '').replace(/^=+\s*/, '');

    // In dual/alternate units (e.g. "25.00 QTL = 100 BAG"), parse each segment
    const rawSegments = s.split('=').map((seg) => seg.trim()).filter((seg) => /\d/.test(seg));
    if (rawSegments.length > 0) {
      interface ParsedSegment {
        quantity: number;
        unit?: string;
        raw: string;
      }
      const parsedSegments: ParsedSegment[] = [];
      for (const seg of rawSegments) {
        const match = seg.match(/[-+]?\d*\.?\d+/);
        if (!match) continue;
        const parsed = Math.abs(parseFloat(match[0]));
        if (isNaN(parsed) || parsed <= 0) continue;
        const rest = seg.replace(match[0], '').trim();
        const unitMatch = rest.match(/[a-zA-Z]+/);
        const unit = unitMatch ? unitMatch[0] : undefined;
        parsedSegments.push({ quantity: parsed, unit, raw: seg });
      }

      if (parsedSegments.length > 0) {
        // 1. Prioritize BAG / BAGS / BGS / BG over weight units like QTL / KGS
        const isBag = (u?: string) => !!u && /^(bag|bags|bgs|bg)$/i.test(u);
        const bagSegment = parsedSegments.find((p) => isBag(p.unit));
        if (bagSegment) {
          return { quantity: bagSegment.quantity, unit: bagSegment.unit };
        }

        // 2. If one segment is packaging/count and another is bulk weight (QTL, KGS, etc.), prefer count
        const isWeight = (u?: string) =>
          !!u && /^(qtl|qntl|quintal|quintals|kg|kgs|mt|ton|tons|tonne|tonnes)$/i.test(u);
        const nonWeight = parsedSegments.find((p) => p.unit && !isWeight(p.unit));
        if (nonWeight && parsedSegments.some((p) => isWeight(p.unit))) {
          return { quantity: nonWeight.quantity, unit: nonWeight.unit };
        }

        // 3. Fallback to primary (first) segment
        return { quantity: parsedSegments[0].quantity, unit: parsedSegments[0].unit };
      }
    }
  }

  // If passed directly as a numeric value
  if (typeof rawVal === 'number' && !isNaN(rawVal) && Math.abs(rawVal) > 0) {
    return { quantity: Math.abs(rawVal) };
  }

  // Check batch allocations if top-level quantity was 0 or empty
  if (batches && batches.length > 0) {
    let sum = 0;
    let batchUnit: string | undefined;
    for (const b of batches) {
      const bRes = parseCleanQuantity(b.quantity, b.billed_qty);
      if (bRes.quantity > 0) {
        sum += bRes.quantity;
        if (!batchUnit && bRes.unit) batchUnit = bRes.unit;
      }
    }
    if (sum > 0) {
      return { quantity: Math.round(sum * 1000) / 1000, unit: batchUnit };
    }
  }

  // If rate and amount exist, deduce quantity = amount / rate
  if (amount && rate && Math.abs(rate) > 0) {
    const computed = Math.round((Math.abs(amount) / Math.abs(rate)) * 100) / 100;
    if (computed > 0) {
      return { quantity: computed };
    }
  }

  return { quantity: 1 };
};

export const parseCleanRate = (
  rateVal?: number | string,
  rateRaw?: string,
  amount?: number,
  quantity?: number
): number => {
  const candidates = [rateRaw, typeof rateVal === 'string' ? rateVal : ''];
  for (const str of candidates) {
    if (!str || typeof str !== 'string') continue;
    // Rates in Tally are formatted like "2500.00/Bag" or "100.00/Nos"
    const part = str.replace(/,/g, '').split('/')[0].trim();
    const match = part.match(/[-+]?\d*\.?\d+/);
    if (match) {
      const parsed = Math.abs(parseFloat(match[0]));
      if (!isNaN(parsed) && parsed > 0) return parsed;
    }
  }

  if (typeof rateVal === 'number' && !isNaN(rateVal) && rateVal > 0) {
    return Math.abs(rateVal);
  }

  if (amount && quantity && quantity > 0) {
    return Math.round((Math.abs(amount) / quantity) * 100) / 100;
  }

  return 0;
};

/** Helper: Normalize various date formats to ISO format (YYYY-MM-DD) */
export const normalizeVoucherDate = (raw?: string | Date): string => {
  if (!raw) return new Date().toISOString().slice(0, 10);

  const rawStr = String(raw).trim();

  // Already in YYYY-MM-DD format
  if (/^\d{4}-\d{2}-\d{2}$/.test(rawStr)) {
    return rawStr;
  }

  // Compact format: YYYYMMDD
  if (/^\d{8}$/.test(rawStr)) {
    return `${rawStr.slice(0, 4)}-${rawStr.slice(4, 6)}-${rawStr.slice(6, 8)}`;
  }

  // Try parsing as Date
  const parsed = new Date(rawStr);
  if (!isNaN(parsed.getTime())) {
    return parsed.toISOString().slice(0, 10);
  }

  return new Date().toISOString().slice(0, 10);
};

/** Helper: Extract party information safely from voucher */
export const extractPartyInfo = (v: VoucherItem) => {
  return {
    name: v.party?.name || v.party?.ledger_name || 'N/A',
    gstin: v.party?.gstin || undefined,
    state: v.party?.state || undefined,
  };
};

/** Converts a live Tally voucher into a SaleRecord shape for PDF generation. */
export const mapVoucherToSaleRecord = (v: VoucherItem): SaleRecord => {
  const dateISO = normalizeVoucherDate(v.date);

  const rawItems = v.inventory_entries || [];
  const items: SaleItem[] = rawItems.map((item: InventoryItem) => {
    const amount = Math.abs(Number(item.amount) || 0);
    const qtyInfo = parseCleanQuantity(
      item.quantity,
      item.billed_qty,
      item.batches,
      amount,
      typeof item.rate === 'number' ? item.rate : undefined
    );
    const rate = parseCleanRate(item.rate, item.rate_raw, amount, qtyInfo.quantity);
    return {
      name: item.item_name || 'Item',
      quantity: qtyInfo.quantity,
      rate,
      amount,
      unit: qtyInfo.unit || item.unit,
      billed_qty: item.billed_qty,
    };
  });

  const totalAmount =
    v.total_amount !== undefined && v.total_amount !== null && v.total_amount > 0
      ? v.total_amount
      : items.length > 0
        ? items.reduce((sum, item) => sum + item.amount, 0)
        : v.ledger_entries && v.ledger_entries.length > 0
          ? v.ledger_entries.reduce((sum, item) => sum + Math.abs(Number(item.amount) || 0), 0)
          : 0;
  const totalGst =
    (v.taxes?.cgst || 0) + (v.taxes?.sgst || 0) + (v.taxes?.igst || 0) || undefined;

  const partyInfo = extractPartyInfo(v);
  const truckNumber = v.vehicle_number || undefined;

  return {
    voucherNumber: v.voucher_number || 'N/A',
    voucherType: v.voucher_type,
    dateISO,
    partyName: partyInfo.name,
    partyState: partyInfo.state,
    partyGstin: partyInfo.gstin,
    narration: v.narration || undefined,
    truckNumber,
    items,
    totalAmount,
    totalGst,
    reference: v.reference || undefined,
    invoiceNumber: v.voucher_number || undefined,
  };
};
