import type {
  Content,
  TableCell,
  TDocumentDefinitions,
} from 'pdfmake/interfaces';
import type { SaleItem, SaleRecord } from '../models/bill.model';
import { parseCleanQuantity } from './bill.mapper';
import { CompanyProfile } from '../models/company.model';

const indianFormat = (n: number | undefined | null): string => {
  const num = typeof n === 'number' && !isNaN(n) ? n : 0;
  const [intPart, decPart] = num.toFixed(2).split('.');
  const lastThree = intPart.slice(-3);
  const rest = intPart.slice(0, -3);
  const formatted = rest
    ? rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + ',' + lastThree
    : lastThree;
  return decPart === '00' ? formatted : `${formatted}.${decPart}`;
};

const C = {
  gold: '#a68422',
  goldLight: '#caa030',
  text: '#1f2937',
  textLight: '#6b7280',
  textMuted: '#9ca3af',
  border: '#e5e7eb',
  rowAlt: '#f9fafb',
  white: '#ffffff',
};

function getPdfDensity(itemCount: number) {
  if (itemCount > 30) {
    return { itemFontSize: 4.5, tablePadding: 0, headerPadding: 0, logoSize: 16, compact: true, ultraCompact: true };
  }
  if (itemCount > 22) {
    return { itemFontSize: 5, tablePadding: 0, headerPadding: 1, logoSize: 20, compact: true, ultraCompact: true };
  }
  if (itemCount > 15) {
    return { itemFontSize: 6, tablePadding: 0, headerPadding: 2, logoSize: 24, compact: true, ultraCompact: false };
  }
  if (itemCount > 10) {
    return { itemFontSize: 6.5, tablePadding: 1, headerPadding: 3, logoSize: 32, compact: true, ultraCompact: false };
  }
  return { itemFontSize: 8, tablePadding: 3, headerPadding: 6, logoSize: 55, compact: false, ultraCompact: false };
}

function formatDate(iso: string): string {
    const [y, m, d] = iso.split('-');
    return `${d}/${m}/${y.slice(2)}`;
  }

function formatItemQty(item: SaleItem): string {
    // If raw billed_qty string has dual units (e.g. '25.00 QTL = 100 BAG'), ensure BAG count is picked
    const rawQty = (item as any).billed_qty;
    if (typeof rawQty === 'string' && rawQty.includes('=')) {
      const parsed = parseCleanQuantity(undefined, rawQty);
      if (parsed.quantity > 0) {
        return String(parsed.quantity);
      }
    }
    return item.quantity != null ? String(item.quantity) : '';
  }

export function buildInvoiceDoc(sale: SaleRecord, config: CompanyProfile, logoDataUri: string): TDocumentDefinitions {
    const dateStr = formatDate(sale.dateISO);
    const density = getPdfDensity(sale.items.length);

    const subtotal = sale.totalGst != null
      ? sale.totalAmount - sale.totalGst
      : sale.totalAmount;
    const grandTotal = sale.totalGst != null
      ? sale.totalAmount
      : sale.totalAmount;

    // ── Header banner ──────────────────────────────────────────────
    const headerBanner: Content = {
      stack: [
        {
          table: {
            widths: [70, '*'],
            body: [
              [
                {
                  image: logoDataUri,
                  fit: [density.logoSize, density.logoSize],
                  margin: [0, 0, 0, 0],
                  border: [false, false, false, false],
                },
                {
                  stack: [
                    {
                      text: config.company_name,
                      style: 'companyName',
                    },
                    ...(config.tagline ? [{ text: config.tagline, style: 'companyTagline', margin: [0, density.ultraCompact ? 0 : 1, 0, 0] as [number, number, number, number] }] : []),
                    {
                      text: config.address,
                      style: 'companySub',
                      margin: [0, density.ultraCompact ? 0 : 2, 0, 0] as [number, number, number, number],
                    },
                    {
                      text: [
                        { text: `GSTIN: ${config.gstin}`, bold: true },
                        ...(config.pan ? [{ text: `  |  PAN: ${config.pan}` }] : []),
                        ...(config.state ? [{ text: `  |  State: ${config.state}` }] : []),
                      ],
                      style: 'companySub',
                      margin: [0, density.ultraCompact ? 0 : 2, 0, 0] as [number, number, number, number],
                    },
                    ...((config.phone || config.email) ? [{
                      text: [
                        ...(config.phone ? [{ text: `Phone: ${config.phone}` }] : []),
                        ...(config.phone && config.email ? [{ text: '  |  ' }] : []),
                        ...(config.email ? [{ text: `Email: ${config.email}` }] : []),
                      ],
                      style: 'companySub',
                      margin: [0, density.ultraCompact ? 0 : 1, 0, 0] as [number, number, number, number],
                    }] : []),
                  ],
                  border: [false, false, false, false],
                  margin: [10, 0, 0, 0],
                },
              ],
            ],
          },
          layout: {
            hLineWidth: () => 0,
            vLineWidth: () => 0,
            paddingLeft: () => 8,
            paddingRight: () => 8,
            paddingTop: () => density.headerPadding,
            paddingBottom: () => density.headerPadding,
          },
        },
        {
          canvas: [
            {
              type: 'line',
              x1: 0,
              y1: 0,
              x2: 530,
              y2: 0,
              lineWidth: 1.5,
              lineColor: C.gold,
            },
          ],
          margin: [0, 0, 0, density.compact ? 3 : 6],
        },
      ],
    };

    // ── Invoice details row ────────────────────────────────────────
    const invoiceInfo: Content = {
      table: {
        widths: ['*', 'auto'],
        body: [
          [
            {
              stack: [
                { text: 'BILL TO', style: 'sectionLabel' },
                { text: sale.partyName, style: 'infoValueBold', margin: [0, density.ultraCompact ? 0 : 3, 0, 0] as [number, number, number, number] },
                ...(sale.partyAddress
                  ? [{ text: sale.partyAddress, style: 'infoSmall', margin: [0, density.ultraCompact ? 0 : 2, 0, 0] as [number, number, number, number] }]
                  : []),
                ...(sale.partyState
                  ? [{ text: `State: ${sale.partyState}`, style: 'infoSmall', margin: [0, density.ultraCompact ? 0 : 1, 0, 0] as [number, number, number, number] }]
                  : []),
                ...(sale.partyGstin
                  ? [{ text: `GSTIN: ${sale.partyGstin}`, style: 'infoSmall', margin: [0, density.ultraCompact ? 0 : 1, 0, 0] as [number, number, number, number] }]
                  : []),
              ],
              border: [false, false, false, false],
              margin: [0, 0, 0, 0] as [number, number, number, number],
            },
            {
              stack: [
                { text: 'DATE', style: 'sectionLabel', alignment: 'right', margin: [0, density.ultraCompact ? 0 : 4, 0, 0] as [number, number, number, number] },
                { text: dateStr, style: 'infoValueBold', alignment: 'right' },
              ],
              border: [false, false, false, false],
              margin: [0, 0, 0, 0] as [number, number, number, number],
            },
          ],
        ],
      },
      layout: {
        hLineWidth: () => 0,
        vLineWidth: () => 0,
        paddingLeft: () => 10,
        paddingRight: () => 10,
        paddingTop: () => density.headerPadding,
        paddingBottom: () => density.headerPadding,
      },
      margin: [0, 0, 0, 8] as [number, number, number, number],
    };

    // ── Items table ────────────────────────────────────────────────
    const tableHeader: TableCell[] = [
      { text: '#', style: 'tableHeader', alignment: 'center', border: [false, false, false, false] },
      { text: 'ITEM', style: 'tableHeader', border: [false, false, false, false] },
      { text: 'QTY', style: 'tableHeader', alignment: 'center', border: [false, false, false, false] },
      { text: 'RATE', style: 'tableHeader', alignment: 'right', border: [false, false, false, false] },
      { text: 'AMOUNT', style: 'tableHeader', alignment: 'right', border: [false, false, false, false] },
    ];

    const itemRows: any[][] = sale.items.map((item, i) => {
      const isAlt = i % 2 === 1;
      return [
        {
          text: String(i + 1),
          style: 'itemCell',
          alignment: 'center',
          border: [false, false, false, false],
          fillColor: isAlt ? C.rowAlt : null,
        },
        {
          text: item.name,
          style: 'itemCellBold',
          border: [false, false, false, false],
          fillColor: isAlt ? C.rowAlt : null,
        },
        {
          text: formatItemQty(item),
          style: 'itemCell',
          alignment: 'center',
          border: [false, false, false, false],
          fillColor: isAlt ? C.rowAlt : null,
        },
        {
          text: indianFormat(item.rate),
          style: 'itemCell',
          alignment: 'right',
          border: [false, false, false, false],
          fillColor: isAlt ? C.rowAlt : null,
        },
        {
          text: indianFormat(item.amount),
          style: 'itemCellBold',
          alignment: 'right',
          border: [false, false, false, false],
          fillColor: isAlt ? C.rowAlt : null,
        },
      ];
    });

    const itemsTable: Content = {
      table: {
        widths: [25, '*', 65, 65, 75],
        headerRows: 1,
        body: [tableHeader, ...itemRows],
      },
      layout: {
        hLineWidth: (i) => (i === 1 ? 1 : 0),
        vLineWidth: () => 0,
        hLineColor: () => C.border,
        paddingLeft: () => density.compact ? 3 : 6,
        paddingRight: () => density.compact ? 3 : 6,
        paddingTop: () => density.tablePadding,
        paddingBottom: () => density.tablePadding,
        fillColor: (rowIndex) => {
          if (rowIndex === 0) return '#f5f3e8';
          return null;
        },
      },
      margin: [0, 0, 0, 8] as [number, number, number, number],
    };

    // ── Totals ─────────────────────────────────────────────────────
    const totalRows: any[][] = [];

    totalRows.push([
      { text: '', border: [false, false, false, false], colSpan: 3 },
      { text: '', border: [false, false, false, false] },
      { text: '', border: [false, false, false, false] },
      {
        text: 'Subtotal',
        style: 'totalLabel',
        alignment: 'right',
        border: [false, false, false, false],
      },
      {
        text: indianFormat(subtotal),
        style: 'totalValue',
        alignment: 'right',
        border: [false, false, false, false],
      },
    ]);

    if (sale.totalGst != null && sale.totalGst > 0) {
      totalRows.push([
        { text: '', border: [false, false, false, false], colSpan: 3 },
        { text: '', border: [false, false, false, false] },
        { text: '', border: [false, false, false, false] },
        {
          text: 'GST',
          style: 'totalLabel',
          alignment: 'right',
          border: [false, false, false, false],
        },
        {
          text: indianFormat(sale.totalGst),
          style: 'totalValue',
          alignment: 'right',
          border: [false, false, false, false],
        },
      ]);
    }

    totalRows.push([
      { text: '', border: [false, false, false, false], colSpan: 3 },
      { text: '', border: [false, false, false, false] },
      { text: '', border: [false, false, false, false] },
      {
        text: 'TOTAL',
        style: 'grandTotalLabel',
        alignment: 'right',
        border: [false, false, false, false],
      },
      {
        text: indianFormat(grandTotal),
        style: 'grandTotalValue',
        alignment: 'right',
        border: [false, false, false, false],
      },
    ]);

    const totalsBlock: Content = {
      table: {
        widths: ['*', '*', '*', 60, 75],
        body: totalRows,
      },
      layout: {
        hLineWidth: (i) => (i === totalRows.length - 1 ? 1.5 : 0),
        vLineWidth: () => 0,
        hLineColor: () => C.gold,
        paddingLeft: () => 6,
        paddingRight: () => 6,
        paddingTop: () => density.tablePadding,
        paddingBottom: () => density.tablePadding,
      },
      margin: [0, 0, 0, 6] as [number, number, number, number],
    };

    // ── Assemble ───────────────────────────────────────────────────
    const body: Content[] = [
      headerBanner,
      invoiceInfo,
      itemsTable,
      totalsBlock,
    ];

    return {
      pageSize: 'A5',
      pageOrientation: 'landscape',
      pageMargins: [12, density.compact ? 2 : 8, 12, density.compact ? 10 : 24],
      content: body,
      footer: (currentPage: number, pageCount: number): Content => ({
        margin: [15, 0, 15, 0],
        stack: [
          {
            canvas: [
              {
                type: 'line',
                x1: 0,
                y1: 0,
                x2: 515,
                y2: 0,
                lineWidth: 0.5,
                lineColor: C.gold,
              },
            ],
            margin: [0, 0, 0, 4],
          },
          {
            columns: [
              {
                text: 'Thank you for your business!',
                style: 'footerText',
                width: '*',
              },
              {
                text: `Page ${currentPage} of ${pageCount}`,
                style: 'footerMuted',
                width: 'auto',
                alignment: 'right',
              },
            ],
          },
        ],
      }),
      styles: {
        companyName: {
          fontSize: density.ultraCompact ? 9 : density.compact ? 12 : 16,
          bold: true,
          color: C.gold,
        },
        companyTagline: {
          fontSize: density.ultraCompact ? 5 : density.compact ? 6.5 : 8,
          italics: true,
          color: '#8a7e50',
        },
        companySub: {
          fontSize: density.ultraCompact ? 5 : density.compact ? 6.5 : 8,
          color: '#8a7e50',
        },
        invoiceTitle: {
          fontSize: 11,
          bold: true,
          color: C.white,
          alignment: 'right',
          characterSpacing: 2,
        },
        sectionLabel: {
          fontSize: density.ultraCompact ? 5 : density.compact ? 6 : 7,
          bold: true,
          color: C.goldLight,
          characterSpacing: 1.5,
        },
        infoLabel: {
          fontSize: 7.5,
          color: C.textMuted,
        },
        infoValue: {
          fontSize: 9,
          color: C.text,
        },
        infoValueBold: {
          fontSize: density.ultraCompact ? 5.5 : density.compact ? 7.5 : 9,
          bold: true,
          color: C.text,
        },
        infoSmall: {
          fontSize: density.ultraCompact ? 5 : density.compact ? 6.5 : 7.5,
          color: C.textLight,
        },
        tableHeader: {
          fontSize: density.compact ? 6 : 7.5,
          bold: true,
          color: C.gold,
          characterSpacing: 0.5,
        },
        itemCell: {
          fontSize: density.itemFontSize,
          color: C.text,
        },
        itemCellBold: {
          fontSize: density.itemFontSize,
          bold: true,
          color: C.text,
        },
        totalLabel: {
          fontSize: density.ultraCompact ? 6 : 8.5,
          color: C.textLight,
        },
        totalValue: {
          fontSize: density.ultraCompact ? 6 : 8.5,
          color: C.text,
        },
        grandTotalLabel: {
          fontSize: density.ultraCompact ? 7 : 9.5,
          bold: true,
          color: C.gold,
        },
        grandTotalValue: {
          fontSize: density.ultraCompact ? 8 : 10,
          bold: true,
          color: C.gold,
        },
        footerText: {
          fontSize: 7,
          color: C.textMuted,
          italics: true,
        },
        docBadge: {
          fontSize: density.compact ? 7 : 8.5,
          bold: true,
          color: C.gold,
          characterSpacing: 1.5,
        },
        docBadgeBlue: {
          fontSize: 8.5,
          bold: true,
          color: '#1d4ed8',
          characterSpacing: 1.5,
        },
        footerMuted: {
          fontSize: 6.5,
          color: C.textMuted,
        },
      },
      defaultStyle: {
        font: 'Lexend',
      },
    };
  }

export function buildDeliveryNoteDoc(sale: SaleRecord, config: CompanyProfile, logoDataUri: string): TDocumentDefinitions {
    const dateStr = formatDate(sale.dateISO);
    const density = getPdfDensity(sale.items.length);
    const isTaxable = sale.voucherType?.trim().toUpperCase() === 'RICE SALES TAXABLE';

    // ── Header banner ──────────────────────────────────────────────
    const headerBanner: Content = {
      stack: [
        {
          table: {
            widths: [70, '*'],
            body: [
              [
                {
                  image: logoDataUri,
                  fit: [density.logoSize, density.logoSize],
                  margin: [0, 0, 0, 0],
                  border: [false, false, false, false],
                },
                {
                  stack: [
                    {
                      text: config.company_name,
                      style: 'companyName',
                    },
                    ...(config.tagline ? [{ text: config.tagline, style: 'companyTagline', margin: [0, density.ultraCompact ? 0 : 1, 0, 0] as [number, number, number, number] }] : []),
                    {
                      text: config.address,
                      style: 'companySub',
                      margin: [0, density.ultraCompact ? 0 : 2, 0, 0] as [number, number, number, number],
                    },
                    {
                      text: [
                        { text: `GSTIN: ${config.gstin}`, bold: true },
                        ...(config.pan ? [{ text: `  |  PAN: ${config.pan}` }] : []),
                        ...(config.state ? [{ text: `  |  State: ${config.state}` }] : []),
                      ],
                      style: 'companySub',
                      margin: [0, density.ultraCompact ? 0 : 2, 0, 0] as [number, number, number, number],
                    },
                    ...((config.phone || config.email) ? [{
                      text: [
                        ...(config.phone ? [{ text: `Phone: ${config.phone}` }] : []),
                        ...(config.phone && config.email ? [{ text: '  |  ' }] : []),
                        ...(config.email ? [{ text: `Email: ${config.email}` }] : []),
                      ],
                      style: 'companySub',
                      margin: [0, density.ultraCompact ? 0 : 1, 0, 0] as [number, number, number, number],
                    }] : []),
                  ],
                  border: [false, false, false, false],
                  margin: [10, 0, 0, 0],
                },
              ],
            ],
          },
          layout: {
            hLineWidth: () => 0,
            vLineWidth: () => 0,
            paddingLeft: () => 8,
            paddingRight: () => 8,
            paddingTop: () => density.headerPadding,
            paddingBottom: () => density.headerPadding,
          },
        },
        {
          canvas: [
            {
              type: 'line',
              x1: 0,
              y1: 0,
              x2: 530,
              y2: 0,
              lineWidth: 1.5,
              lineColor: C.gold,
            },
          ],
          margin: [0, 0, 0, density.compact ? 3 : 6],
        },
      ],
    };

    // ── Delivery & Consignee Info Row ──────────────────────────────
    const dispatchInfo: Content = {
      table: {
        widths: ['*', 180],
        body: [
          [
            {
              stack: [
                { text: 'DISPATCH / CONSIGNEE', style: 'sectionLabel' },
                { text: sale.partyName, style: 'infoValueBold', margin: [0, density.ultraCompact ? 0 : 3, 0, 0] as [number, number, number, number] },
                ...(sale.partyAddress
                  ? [{ text: sale.partyAddress, style: 'infoSmall', margin: [0, density.ultraCompact ? 0 : 2, 0, 0] as [number, number, number, number] }]
                  : []),
                ...(sale.partyState
                  ? [{ text: `State: ${sale.partyState}`, style: 'infoSmall', margin: [0, density.ultraCompact ? 0 : 1, 0, 0] as [number, number, number, number] }]
                  : []),
                ...(sale.partyGstin
                  ? [{ text: `GSTIN: ${sale.partyGstin}`, style: 'infoSmall', margin: [0, density.ultraCompact ? 0 : 1, 0, 0] as [number, number, number, number] }]
                  : []),
              ],
              border: [false, false, false, false],
              margin: [0, 0, 0, 0] as [number, number, number, number],
            },
            {
              stack: [
                { text: 'DELIVERY CHALLAN / NOTE', style: 'docBadge', alignment: 'right' },
                { text: 'DISPATCH DATE', style: 'sectionLabel', alignment: 'right', margin: [0, density.ultraCompact ? 0 : 3, 0, 0] as [number, number, number, number] },
                { text: dateStr, style: 'infoValueBold', alignment: 'right' },
              ],
              border: [false, false, false, false],
              margin: [0, 0, 0, 0] as [number, number, number, number],
            },
          ],
        ],
      },
      layout: {
        hLineWidth: () => 0,
        vLineWidth: () => 0,
        paddingLeft: () => 10,
        paddingRight: () => 10,
        paddingTop: () => density.headerPadding,
        paddingBottom: () => density.headerPadding,
      },
      margin: [0, 0, 0, 6] as [number, number, number, number],
    };

    // ── Items Table ────────────────────────────────────────────────
    const tableHeader: TableCell[] = [
      { text: '#', style: 'tableHeader', alignment: 'center', border: [false, false, false, false] },
      { text: 'DESCRIPTION OF GOODS', style: 'tableHeader', border: [false, false, false, false] },
      { text: 'DISPATCHED QTY', style: 'tableHeader', alignment: 'center', border: [false, false, false, false] },
      { text: 'PRICE / UNIT', style: 'tableHeader', alignment: 'right', border: [false, false, false, false] },
    ];

    let totalQuantity = 0;
    const itemRows: any[][] = sale.items.map((item, i) => {
      const isAlt = i % 2 === 1;
      const qtyStr = formatItemQty(item);
      const parsedNum = parseFloat(qtyStr);
      if (!isNaN(parsedNum)) {
        totalQuantity += parsedNum;
      }
      return [
        {
          text: String(i + 1),
          style: 'itemCell',
          alignment: 'center',
          border: [false, false, false, false],
          fillColor: isAlt ? C.rowAlt : null,
        },
        {
          text: item.name,
          style: 'itemCellBold',
          border: [false, false, false, false],
          fillColor: isAlt ? C.rowAlt : null,
        },
        {
          text: qtyStr || '—',
          style: 'itemCellBold',
          alignment: 'center',
          border: [false, false, false, false],
          fillColor: isAlt ? C.rowAlt : null,
        },
        {
          text: `₹ ${indianFormat(item.rate)}${isTaxable ? ' + GST' : ''}`,
          style: 'itemCell',
          alignment: 'right',
          border: [false, false, false, false],
          fillColor: isAlt ? C.rowAlt : null,
        },
      ];
    });

    const itemsTable: Content = {
      table: {
        widths: [25, '*', 100, 110],
        headerRows: 1,
        body: [tableHeader, ...itemRows],
      },
      layout: {
        hLineWidth: (i) => (i === 1 ? 1 : 0),
        vLineWidth: () => 0,
        hLineColor: () => C.border,
        paddingLeft: () => density.compact ? 3 : 6,
        paddingRight: () => density.compact ? 3 : 6,
        paddingTop: () => density.tablePadding,
        paddingBottom: () => density.tablePadding,
        fillColor: (rowIndex) => {
          if (rowIndex === 0) return '#f5f3e8';
          return null;
        },
      },
      margin: [0, 0, 0, 6] as [number, number, number, number],
    };

    // ── Total Quantity Block ───────────────────────────────────────
    const totalsBlock: Content = {
      table: {
        widths: ['*', 110],
        body: [
          [
            { text: 'TOTAL QUANTITY:', style: 'grandTotalLabel', alignment: 'right', border: [false, false, false, false] },
            { text: String(totalQuantity || '—'), style: 'grandTotalValue', alignment: 'center', border: [false, false, false, false] },
          ]
        ],
      },
      layout: {
        hLineWidth: (i) => (i === 1 ? 1.5 : 0),
        vLineWidth: () => 0,
        hLineColor: () => C.gold,
        paddingLeft: () => 6,
        paddingRight: () => 6,
        paddingTop: () => density.tablePadding,
        paddingBottom: () => density.tablePadding,
      },
      margin: [0, 0, 0, 8] as [number, number, number, number],
    };

    // ── Dispatcher signature ──────────────────────────────────────
    const signBlock: Content = {
      stack: [
        { text: '_________________________', alignment: 'right', color: '#c4bc96', fontSize: density.compact ? density.itemFontSize : 8 },
        { text: 'Dispatcher / Sender Signature', fontSize: density.compact ? 5 : 7, color: C.textLight, alignment: 'right' },
      ],
      margin: [0, density.compact ? 2 : 4, 0, 0] as [number, number, number, number],
    };

    const body: Content[] = [
      headerBanner,
      dispatchInfo,
      itemsTable,
      totalsBlock,
      signBlock,
    ];

    return {
      pageSize: 'A5',
      pageOrientation: 'landscape',
      pageMargins: [12, density.compact ? 2 : 8, 12, density.compact ? 10 : 24],
      content: body,
      footer: (currentPage: number, pageCount: number): Content => ({
        margin: [15, 0, 15, 0],
        stack: [
          {
            canvas: [
              {
                type: 'line',
                x1: 0,
                y1: 0,
                x2: 515,
                y2: 0,
                lineWidth: 0.5,
                lineColor: C.gold,
              },
            ],
            margin: [0, 0, 0, 4],
          },
          {
            columns: [
              {
                text: 'No rent or freight is payable for the above goods.',
                style: 'footerText',
                width: '*',
              },
              {
                text: `Page ${currentPage} of ${pageCount}`,
                style: 'footerMuted',
                width: 'auto',
                alignment: 'right',
              },
            ],
          },
        ],
      }),
      styles: {
        companyName: {
          fontSize: density.ultraCompact ? 9 : density.compact ? 12 : 16,
          bold: true,
          color: C.gold,
        },
        companyTagline: {
          fontSize: density.ultraCompact ? 5 : density.compact ? 6.5 : 8,
          italics: true,
          color: '#8a7e50',
        },
        companySub: {
          fontSize: density.ultraCompact ? 5 : density.compact ? 6.5 : 8,
          color: '#8a7e50',
        },
        docBadge: {
          fontSize: density.compact ? 7 : 8.5,
          bold: true,
          color: C.gold,
          characterSpacing: 1.5,
        },
        sectionLabel: {
          fontSize: density.ultraCompact ? 5 : density.compact ? 6 : 7,
          bold: true,
          color: C.goldLight,
          characterSpacing: 1.5,
        },
        infoValueBold: {
          fontSize: density.ultraCompact ? 5.5 : density.compact ? 7.5 : 9,
          bold: true,
          color: C.text,
        },
        infoSmall: {
          fontSize: density.ultraCompact ? 5 : density.compact ? 6.5 : 7.5,
          color: C.textLight,
        },
        tableHeader: {
          fontSize: density.compact ? 6 : 7.5,
          bold: true,
          color: C.gold,
          characterSpacing: 0.5,
        },
        itemCell: {
          fontSize: density.itemFontSize,
          color: C.text,
        },
        itemCellBold: {
          fontSize: density.itemFontSize,
          bold: true,
          color: C.text,
        },
        grandTotalLabel: {
          fontSize: density.ultraCompact ? 6.5 : 9,
          bold: true,
          color: C.gold,
        },
        grandTotalValue: {
          fontSize: density.ultraCompact ? 7 : 10.5,
          bold: true,
          color: C.gold,
        },
        footerText: {
          fontSize: 7,
          color: C.textMuted,
          italics: true,
        },
        footerMuted: {
          fontSize: 6.5,
          color: C.textMuted,
        },
      },
      defaultStyle: {
        font: 'Lexend',
      },
    };
  }
