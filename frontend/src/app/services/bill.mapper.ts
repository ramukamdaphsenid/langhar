import { SaleItem, SaleRecord } from '../models/bill.model';
import type { VoucherItem } from '../models/tally-voucher.model';

export interface TallyLineEntry {
  ITEMNAME?: string;
  BILLEDQTY?: number | string;
  ACTUALQTY?: number | string;
  RATE?: number | string;
  AMOUNT?: number | string;
}

export const parseCleanQuantity = (
  rawVal?: number | string,
  billedQtyStr?: string,
  actualQtyStr?: string,
  batches?: any[],
  amount?: number,
  rate?: number
): { quantity: number; unit?: string } => {
  const candidates = [billedQtyStr, actualQtyStr, typeof rawVal === 'string' ? rawVal : ''];

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
      const bRes = parseCleanQuantity(b.quantity, b.billed_qty, b.actual_qty);
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

const toNumber = (value: number | string | undefined): number => {
  if (typeof value === 'string') {
    const clean = value.replace(/,/g, '').split('=')[0].split('/')[0];
    const match = clean.match(/[-+]?\d*\.?\d+/);
    if (match) {
      const n = Math.abs(parseFloat(match[0]));
      return isNaN(n) ? 0 : n;
    }
    return 0;
  }
  return typeof value === 'number' && !isNaN(value) ? Math.abs(value) : 0;
};

const pad = (n: number): string => String(n).padStart(2, '0');

/** Tally yields 8-digit dates; tries YYYYMMDD first, falls back to DDMMYYYY. */
export const parseTallyDate = (raw?: string): Date => {
  if (!raw) return new Date();
  const digits = raw.replace(/[^0-9]/g, '');
  if (digits.length === 8) {
    const year = Number(digits.slice(0, 4));
    const month = Number(digits.slice(4, 6));
    const day = Number(digits.slice(6, 8));
    const isoFirst =
      year >= 1900 && year <= 2200 && month >= 1 && month <= 12 && day >= 1 && day <= 31;
    if (isoFirst) return new Date(year, month - 1, day);
    const dd = Number(digits.slice(0, 2));
    const mm = Number(digits.slice(2, 4));
    const yyyy = Number(digits.slice(4, 8));
    return new Date(yyyy, mm - 1, dd);
  }
  if (raw.includes('-')) {
    const iso = new Date(raw);
    if (Number.isNaN(iso.getTime()) === false) return iso;
  }
  return new Date();
};

export const mapLineItem = (entry: TallyLineEntry): SaleItem => {
  const amount = Math.abs(toNumber(entry.AMOUNT));
  const qtyInfo = parseCleanQuantity(
    undefined,
    typeof entry.BILLEDQTY === 'string' ? entry.BILLEDQTY : undefined,
    typeof entry.ACTUALQTY === 'string' ? entry.ACTUALQTY : undefined,
    undefined,
    amount,
    typeof entry.RATE === 'number' ? entry.RATE : undefined
  );
  const rate = parseCleanRate(entry.RATE, undefined, amount, qtyInfo.quantity);
  return {
    name: entry.ITEMNAME ?? '',
    quantity: qtyInfo.quantity,
    rate,
    amount,
    unit: qtyInfo.unit,
    billed_qty: typeof entry.BILLEDQTY === 'string' ? entry.BILLEDQTY : undefined,
  };
};

/** Known Tally field names that may carry a truck/vehicle number. */
const TRUCK_FIELD_KEYS = [
  'BASICSHIPVESSELNO',
  'GOODSVEHICLENUMBER',
  'VATVEHICLENO',
  'VATVEHICLENUMBER',
  'TRANSPORTERVEHICLE2',
];

/** Matches an Indian commercial-vehicle registration plate. */
const PLATE_PATTERN = /\b[A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,2}\s?\d{1,4}\b/;

/** Matches narration/UDF text that names a truck and carries a plate. */
const TRUCK_HINT_PATTERN = /\b(?:truck|vehicl|lorry|\blr\b)\b[^\d]{0,20}?([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,2}\s?\d{1,4})/i;

const hasTruckHint = (text: string): boolean => /truck|vehicl|lorry|\blr\b/i.test(text);

/** Infers the truck/vehicle number from UDF fields, standard Tally transport fields, or the narration. */
export const deriveTruckNumber = (
  udfs?: Record<string, string>,
  narration?: string,
  transportFields?: Record<string, string>,
): string | undefined => {
  if (transportFields) {
    for (const key of TRUCK_FIELD_KEYS) {
      const val = transportFields[key]?.trim();
      if (val) return val;
    }
  }
  const udfEntries = Object.entries(udfs ?? {});
  for (const [key, value] of udfEntries) {
    if (!value) continue;
    if (hasTruckHint(key)) return value.trim();
    const hint = TRUCK_HINT_PATTERN.exec(value);
    if (hint?.[1]) return hint[1];
  }
  for (const [, value] of udfEntries) {
    const plate = PLATE_PATTERN.exec(value);
    if (plate) return plate[0];
  }
  if (narration) {
    const hint = TRUCK_HINT_PATTERN.exec(narration);
    if (hint?.[1]) return hint[1];
  }
  return undefined;
};

/** Escapes a string for use inside a regular expression. */
const escapeRegExp = (text: string): string => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** Returns the text between `<tag>` and `</tag>` in `source`, or undefined. */
const elementText = (source: string, tag: string): string | undefined => {
  const regex = new RegExp(`<${escapeRegExp(tag)}\\b[^>]*>([\\s\\S]*?)<\\/${escapeRegExp(tag)}>`);
  const match = regex.exec(source);
  return match?.[1] ?? undefined;
};

/** Returns every `<tag>…</tag>` block value in `source`. */
const elementBlocks = (source: string, tag: string): string[] => {
  const blocks: string[] = [];
  const regex = new RegExp(`<${escapeRegExp(tag)}\\b[^>]*>([\\s\\S]*?)<\\/${escapeRegExp(tag)}>`, 'g');
  let match: RegExpExecArray | null;
  while ((match = regex.exec(source)) !== null) blocks.push(match[1]);
  return blocks;
};

const trim = (value: string | undefined): string => (value ?? '').trim();

export const ALLOWED_VOUCHER_TYPES = new Set(['RICE SALES', 'RICE SALES TAXABLE']);

export const isAllowedVoucherType = (type: string | undefined | null): boolean => {
  if (!type) return false;
  return ALLOWED_VOUCHER_TYPES.has(type.trim().toUpperCase());
};

/** Extracts the `VCHTYPE` attribute of a `<VOUCHER …>` tag. */
const voucherTypeAttr = (openTag: string): string =>
  /VCHTYPE=["']([^"']*)["']/.exec(openTag)?.[1] ?? '';

/** Parses `<VOUCHER …>` elements from a Tally XML export. */
export const mapSalesXml = (xml: string): SaleRecord[] => {
  const records: SaleRecord[] = [];
  const voucherRegex = /<VOUCHER\b([^>]*)>([\s\S]*?)<\/VOUCHER>/g;
  let match: RegExpExecArray | null;
  let index = 0;

  while ((match = voucherRegex.exec(xml)) !== null) {
    const [, openTag, body] = match;
    const vchType = voucherTypeAttr(openTag) || trim(elementText(body, 'VOUCHERTYPENAME'));
    if (!isAllowedVoucherType(vchType)) continue;

    const items = elementBlocks(body, 'ALLINVENTORYENTRIES.LIST').map((block) =>
      mapLineItem({
        ITEMNAME: trim(elementText(block, 'STOCKITEMNAME')),
        BILLEDQTY: trim(elementText(block, 'BILLEDQTY')),
        ACTUALQTY: trim(elementText(block, 'ACTUALQTY')),
        RATE: trim(elementText(block, 'RATE')),
        AMOUNT: trim(elementText(block, 'AMOUNT')),
      }),
    );
    const total = items.reduce((sum, item) => sum + item.amount, 0);

    const voucherNumber = trim(elementText(body, 'VOUCHERNUMBER')) || String(index + 1);
    const date = parseTallyDate(trim(elementText(body, 'DATE')));
    const partyName =
      trim(elementText(body, 'PARTYLEDGERNAME')) || trim(elementText(body, 'PARTYNAME'));
    const partyGstin = trim(elementText(body, 'PARTYGSTIN')) || trim(elementText(body, 'CMPGSTIN'));
    const narration = trim(elementText(body, 'NARRATION')) || undefined;
    const guid = trim(elementText(body, 'GUID'));

    const udfs: Record<string, string> = {};
    const childRegex = /<([A-Za-z0-9_.:-]+)\b[^>]*>([\s\S]*?)<\/\1>/g;
    let child: RegExpExecArray | null;
    while ((child = childRegex.exec(body)) !== null) {
      if (child[1].startsWith('UDF:')) {
        const value = trim(child[2]);
        if (value) udfs[`udf:${child[1].slice(4)}`] = value;
      }
    }

    const transportFields: Record<string, string> = {};
    for (const key of TRUCK_FIELD_KEYS) {
      const value = trim(elementText(body, key));
      if (value) transportFields[key] = value;
    }

    const totalGst = parseGst(body);

    const deliveryNote =
      udfs['udf:DELIVERYNOTE'] ||
      udfs['udf:DELIVERY NOTE'] ||
      udfs['udf:DELNO'] ||
      trim(elementText(body, 'DELIVERYNOTE')) ||
      undefined;

    records.push({
      voucherNumber,
      voucherType: vchType,
      dateISO: `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
      partyName,
      partyGstin: partyGstin || undefined,
      narration,
      truckNumber: deriveTruckNumber(udfs, narration, transportFields),
      deliveryNote,
      items,
      totalAmount: total,
      totalGst,
      rowId: `${date.getTime()}-${voucherNumber}-${index}-${guid}`,
    });
    index += 1;
  }

  return records;
};

const GST_LEDGER_PATTERN = /\b(?:CGST|SGST|IGST|GST)\b/i;

/** Parses tax ledger entries and returns the total GST amount from the voucher body. */
const parseGst = (body: string): number | undefined => {
  const blocks = elementBlocks(body, 'LEDGERENTRIES.LIST');
  let total = 0;
  let found = false;
  for (const block of blocks) {
    const name = trim(elementText(block, 'LEDGERNAME'));
    if (!GST_LEDGER_PATTERN.test(name)) continue;
    const raw = trim(elementText(block, 'AMOUNT'));
    if (!raw) continue;
    const amount = Math.abs(toNumber(raw));
    if (amount > 0) {
      total += amount;
      found = true;
    }
  }
  return found ? total : undefined;
};

/** Converts a live Tally voucher into a SaleRecord shape for PDF generation. */
export const mapVoucherToSaleRecord = (v: VoucherItem): SaleRecord => {
  let dateISO = '';
  if (v.date) {
    const raw = String(v.date).trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
      dateISO = raw;
    } else if (/^\d{8}$/.test(raw)) {
      dateISO = `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`;
    } else {
      const parsed = new Date(raw);
      if (!isNaN(parsed.getTime())) {
        dateISO = parsed.toISOString().slice(0, 10);
      } else {
        dateISO = new Date().toISOString().slice(0, 10);
      }
    }
  } else {
    dateISO = new Date().toISOString().slice(0, 10);
  }

  const rawItems = v.inventory_entries || v.items || [];
  const items: SaleItem[] = rawItems.map((item: any) => {
    const amount = Math.abs(Number(item.amount) || 0);
    const qtyInfo = parseCleanQuantity(
      item.quantity,
      item.billed_qty,
      item.actual_qty,
      item.batches || item.batch_allocations,
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
      billed_qty: item.billed_qty || item.actual_qty,
    };
  });

  const totalAmount =
    v.total_amount !== undefined && v.total_amount !== null && v.total_amount > 0
      ? v.total_amount
      : items.length > 0
      ? items.reduce((sum, it) => sum + it.amount, 0)
      : v.ledger_entries && v.ledger_entries.length > 0
      ? v.ledger_entries.reduce((sum, it) => sum + Math.abs(Number(it.amount) || 0), 0)
      : 0;

  const totalGst =
    (v.taxes?.cgst || 0) + (v.taxes?.sgst || 0) + (v.taxes?.igst || 0) || undefined;

  const partyName =
    v.party_name || v.party?.name || v.party_ledger_name || v.party?.ledger_name || 'N/A';
  const partyGstin = v.party_gstin || v.party?.gstin || undefined;
  const truckNumber = v.vehicle_number || undefined;
  const deliveryNote = v.reference || undefined;

  const udfs: Record<string, string> = {};
  if (v.state_name || v.party?.state) {
    udfs['State'] = v.state_name || v.party?.state || '';
  }
  if (v.place_of_supply || v.party?.place_of_supply) {
    udfs['Place of Supply'] = v.place_of_supply || v.party?.place_of_supply || '';
  }

  const rowId = v.guid || v.doc_id || `${dateISO}-${v.voucher_number || 'vch'}-${Math.random().toString(36).slice(2, 7)}`;

  const partyAddressRaw = (v as any).party_address || (v as any).party?.address || (v as any).address;
  const partyAddress = Array.isArray(partyAddressRaw)
    ? partyAddressRaw.filter(Boolean).join(', ')
    : (typeof partyAddressRaw === 'string' && partyAddressRaw.trim())
    ? partyAddressRaw.trim()
    : undefined;
  const partyState = v.state_name || v.party?.state || undefined;

  return {
    voucherNumber: v.voucher_number || 'N/A',
    voucherType: v.voucher_type,
    dateISO,
    partyName,
    partyAddress,
    partyState,
    partyGstin,
    narration: v.narration || undefined,
    truckNumber,
    deliveryNote,
    items,
    totalAmount,
    totalGst,
    rowId,
  };
};
