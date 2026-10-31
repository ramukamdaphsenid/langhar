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
  ink: '#111111',
  inkMuted: '#333333',
  textMuted: '#555555',
  border: '#777777',
  tableHeader: '#e5e5e5',
  rowAlt: '#f2f2f2',
  white: '#ffffff',
};

const A5_PAGE_WIDTH = 419.53;
const A5_SIDE_MARGIN = 12;
const A5_PINNING_SPACE = 28;
const A5_CONTENT_TOP_MARGIN = 82;
const A5_CONTENT_WIDTH = A5_PAGE_WIDTH - A5_SIDE_MARGIN * 2;
const INVOICE_TABLE_WIDTHS: (number | string)[] = [22, '*', 55, 55, 65];

function getPdfDensity() {
  return {
    itemFontSize: 8,
    tablePadding: 3,
    headerPadding: 6,
    logoSize: 55,
    compact: false,
    ultraCompact: false,
  };
}

function buildSharedStyles(density: ReturnType<typeof getPdfDensity>) {
  return {
    companyName: {
      fontSize: density.ultraCompact ? 9 : density.compact ? 12 : 16,
      bold: true,
      color: C.ink,
    },
    companyTagline: {
      fontSize: density.ultraCompact ? 5 : density.compact ? 6.5 : 8,
      italics: true,
      color: C.inkMuted,
    },
    companySub: {
      fontSize: density.ultraCompact ? 5 : density.compact ? 6.5 : 8,
      color: C.inkMuted,
    },
    sectionLabel: {
      fontSize: density.ultraCompact ? 5 : density.compact ? 6 : 7,
      bold: true,
      color: C.inkMuted,
      characterSpacing: 1.5,
    },
    infoValueBold: {
      fontSize: density.ultraCompact ? 5.5 : density.compact ? 7.5 : 9,
      bold: true,
      color: C.ink,
    },
    infoSmall: {
      fontSize: density.ultraCompact ? 5 : density.compact ? 6.5 : 7.5,
      color: C.inkMuted,
    },
    tableHeader: {
      fontSize: density.compact ? 6 : 7.5,
      bold: true,
      color: C.ink,
      characterSpacing: 0.5,
    },
    itemCell: {
      fontSize: density.itemFontSize,
      color: C.ink,
    },
    itemCellBold: {
      fontSize: density.itemFontSize,
      bold: true,
      color: C.ink,
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
  };
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

function buildCompanyHeader(
  config: CompanyProfile,
  logoDataUri: string,
  density: ReturnType<typeof getPdfDensity>,
): Content {
  return {
    stack: [
      {
        table: {
          widths: [70, '*'],
          body: [[
            {
              image: logoDataUri,
              fit: [density.logoSize, density.logoSize],
              alignment: 'center',
              verticalAlignment: 'middle',
              margin: [0, 0, 0, 0],
              border: [false, false, false, false],
            },
            {
              stack: [
                { text: config.company_name, style: 'companyName' },
                ...(config.tagline ? [{
                  text: config.tagline,
                  style: 'companyTagline',
                  margin: [0, density.ultraCompact ? 0 : 1, 0, 0] as [number, number, number, number],
                }] : []),
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
          ]],
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
        canvas: [{
          type: 'line',
          x1: 0,
          y1: 0,
          x2: A5_CONTENT_WIDTH,
          y2: 0,
          lineWidth: 1.5,
          lineColor: C.ink,
        }],
        margin: [0, 0, 0, density.compact ? 3 : 6],
      },
    ],
  };
}

function buildDocumentHeader(
  config: CompanyProfile,
  logoDataUri: string,
  density: ReturnType<typeof getPdfDensity>,
): Content {
  return {
    stack: [buildCompanyHeader(config, logoDataUri, density)],
    margin: [0, A5_PINNING_SPACE, 0, 0],
  };
}

function buildPageFooter(text: string) {
  return (currentPage: number, pageCount: number): Content => ({
    margin: [A5_SIDE_MARGIN, 0, A5_SIDE_MARGIN, 0],
    stack: [
      {
        canvas: [{
          type: 'line',
          x1: 0,
          y1: 0,
          x2: A5_CONTENT_WIDTH,
          y2: 0,
          lineWidth: 0.5,
          lineColor: C.ink,
        }],
        margin: [0, 0, 0, 4],
      },
      {
        columns: [
          { text, style: 'footerText', width: '*' },
          {
            text: `Page ${currentPage} of ${pageCount}`,
            style: 'footerMuted',
            width: 'auto',
            alignment: 'right',
          },
        ],
      },
    ],
  });
}

export function buildInvoiceDoc(sale: SaleRecord, config: CompanyProfile, logoDataUri: string): TDocumentDefinitions {
    const dateStr = formatDate(sale.dateISO);
    const density = getPdfDensity();

    const subtotal = sale.totalGst != null
      ? sale.totalAmount - sale.totalGst
      : sale.totalAmount;
    const grandTotal = sale.totalAmount;

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
          text: `₹ ${indianFormat(item.rate)}`,
          style: 'itemCell',
          alignment: 'right',
          border: [false, false, false, false],
          fillColor: isAlt ? C.rowAlt : null,
        },
        {
          text: `₹ ${indianFormat(item.amount)}`,
          style: 'itemCellBold',
          alignment: 'right',
          border: [false, false, false, false],
          fillColor: isAlt ? C.rowAlt : null,
        },
      ];
    });

    const itemsTable: Content = {
      table: {
        widths: [...INVOICE_TABLE_WIDTHS],
        headerRows: 1,
        keepWithHeaderRows: 1,
        dontBreakRows: true,
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
          if (rowIndex === 0) return C.tableHeader;
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
        text: `₹ ${indianFormat(subtotal)}`,
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
          text: `₹ ${indianFormat(sale.totalGst)}`,
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
        text: `₹ ${indianFormat(grandTotal)}`,
        style: 'grandTotalValue',
        alignment: 'right',
        border: [false, false, false, false],
      },
    ]);

    const totalsBlock: Content = {
      table: {
        widths: [...INVOICE_TABLE_WIDTHS],
        body: totalRows,
      },
      layout: {
        hLineWidth: (i) => (i === totalRows.length - 1 ? 1.5 : 0),
        vLineWidth: () => 0,
        hLineColor: () => C.ink,
        paddingLeft: () => 6,
        paddingRight: () => 6,
        paddingTop: () => density.tablePadding,
        paddingBottom: () => density.tablePadding,
      },
      margin: [0, 0, 0, 6] as [number, number, number, number],
      unbreakable: true,
    };

    // ── Assemble ───────────────────────────────────────────────────
    const body: Content[] = [
      invoiceInfo,
      itemsTable,
      totalsBlock,
    ];

    return {
      pageSize: 'A5',
      pageOrientation: 'portrait',
      pageMargins: [12, A5_CONTENT_TOP_MARGIN + A5_PINNING_SPACE, 12, 24],
      header: () => buildDocumentHeader(config, logoDataUri, density),
      content: body,
      footer: (currentPage, pageCount) =>
        buildPageFooter('Thank you for your business!')(currentPage, pageCount),
      styles: {
        ...buildSharedStyles(density),
        totalLabel: {
          fontSize: density.ultraCompact ? 6 : 8.5,
          color: C.inkMuted,
        },
        totalValue: {
          fontSize: density.ultraCompact ? 6 : 8.5,
          color: C.ink,
        },
        grandTotalLabel: {
          fontSize: density.ultraCompact ? 7 : 9.5,
          bold: true,
          color: C.ink,
        },
        grandTotalValue: {
          fontSize: density.ultraCompact ? 8 : 10,
          bold: true,
          color: C.ink,
        },
      },
      defaultStyle: {
        font: 'Lexend',
      },
    };
  }

export function buildDeliveryNoteDoc(sale: SaleRecord, config: CompanyProfile, logoDataUri: string): TDocumentDefinitions {
    const dateStr = formatDate(sale.dateISO);
    const density = getPdfDensity();
    const isTaxable = sale.voucherType?.trim().toUpperCase() === 'RICE SALES TAXABLE';

    // ── Delivery & Consignee Info Row ──────────────────────────────
    const dispatchInfo: Content = {
      table: {
        widths: ['*', 170],
        body: [
          [
            {
              stack: [
                { text: 'DISPATCH / CONSIGNEE', style: 'sectionLabel' },
                { text: sale.partyName, style: 'infoValueBold', margin: [0, density.ultraCompact ? 0 : 3, 0, 0] as [number, number, number, number] },
                ...(sale.partyState
                  ? [{ text: `State: ${sale.partyState}`, style: 'infoSmall', margin: [0, density.ultraCompact ? 0 : 1, 0, 0] as [number, number, number, number] }]
                  : []),
                ...(sale.partyGstin
                  ? [{ text: `GSTIN: ${sale.partyGstin}`, style: 'infoSmall', margin: [0, density.ultraCompact ? 0 : 1, 0, 0] as [number, number, number, number] }]
                  : []),
              ] as Content[],
              border: [false, false, false, false],
              margin: [0, 0, 0, 0] as [number, number, number, number],
            },
            {
              stack: [
                { text: 'DISPATCH DATE', style: 'sectionLabel', alignment: 'right' },
                { text: dateStr, style: 'infoValueBold', alignment: 'right' },
                ...(sale.truckNumber
                  ? [
                    { text: 'VEHICLE NO.', style: 'sectionLabel', alignment: 'right', margin: [0, density.ultraCompact ? 0 : 3, 0, 0] as [number, number, number, number] },
                    { text: sale.truckNumber, style: 'infoValueBold', alignment: 'right' },
                  ]
                  : []),
              ] as Content[],
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
        widths: [22, '*', 85, 95],
        headerRows: 1,
        keepWithHeaderRows: 1,
        dontBreakRows: true,
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
        fillColor: (rowIndex) => rowIndex === 0 ? C.tableHeader : null,
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
            { text: String(totalQuantity || '—'), style: 'grandTotalValue', alignment: 'right', border: [false, false, false, false] },
          ]
        ],
      },
      layout: {
        hLineWidth: (i) => (i === 1 ? 1.5 : 0),
        vLineWidth: () => 0,
        hLineColor: () => C.ink,
        paddingLeft: () => 6,
        paddingRight: () => 6,
        paddingTop: () => density.tablePadding,
        paddingBottom: () => density.tablePadding,
      },
      margin: [0, 0, 0, 8] as [number, number, number, number],
      unbreakable: true,
    };

    // ── Dispatcher signature ──────────────────────────────────────
    const signBlock: Content = {
      columns: [
        {
          width: '*',
          stack: [
            { text: '_________________________', alignment: 'center', color: C.textMuted, fontSize: density.compact ? density.itemFontSize : 8 },
            { text: 'Dispatcher / Sender Signature', fontSize: density.compact ? 5 : 7, color: C.inkMuted, alignment: 'center' },
          ],
        },
        {
          width: '*',
          stack: [
            { text: '_________________________', alignment: 'center', color: C.textMuted, fontSize: density.compact ? density.itemFontSize : 8 },
            { text: 'Received by / Consignee Signature', fontSize: density.compact ? 5 : 7, color: C.inkMuted, alignment: 'center' },
          ],
        },
      ],
      columnGap: 16,
      unbreakable: true,
      margin: [0, density.compact ? 2 : 4, 0, 0] as [number, number, number, number],
    };

    const body: Content[] = [
      dispatchInfo,
      itemsTable,
      totalsBlock,
      signBlock,
    ];

    return {
      pageSize: 'A5',
      pageOrientation: 'portrait',
      pageMargins: [12, A5_CONTENT_TOP_MARGIN + A5_PINNING_SPACE, 12, 24],
      header: () => buildDocumentHeader(config, logoDataUri, density),
      content: body,
      footer: (currentPage, pageCount) =>
        buildPageFooter('No rent or freight is payable for the above goods.')(currentPage, pageCount),
      styles: {
        ...buildSharedStyles(density),
        grandTotalLabel: {
          fontSize: density.ultraCompact ? 6.5 : 9,
          bold: true,
          color: C.ink,
        },
        grandTotalValue: {
          fontSize: density.ultraCompact ? 7 : 10.5,
          bold: true,
          color: C.ink,
        },
      },
      defaultStyle: {
        font: 'Lexend',
      },
    };
  }
