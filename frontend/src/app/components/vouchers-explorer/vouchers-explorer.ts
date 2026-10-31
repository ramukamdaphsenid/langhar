import { Component, ElementRef, HostListener, inject, signal, computed, OnDestroy, viewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { TallyApiService } from '../../services/tally-api.service';
import { VoucherUiUtilsService, DatePreset } from '../../services/voucher-ui-utils.service';
import { BillService } from '../../services/bill.service';
import { VoucherItem } from '../../models/tally-voucher.model';
import { mapVoucherToSaleRecord } from '../../services/bill.mapper';

export type VoucherSortField = 'date' | 'voucher_number' | 'party' | 'amount' | 'items';
export type SortOrder = 'asc' | 'desc';
type PdfAction = 'view-invoice' | 'view-delivery-note' | 'download-invoice' | 'download-delivery-note';

function normalizeDateStr(d: string | undefined | null): string {
  if (!d) return '';
  const s = String(d).trim();
  if (/^\d{8}$/.test(s)) {
    return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`;
  }
  return s.slice(0, 10);
}

@Component({
  selector: 'app-vouchers-explorer',
  standalone: true,
  imports: [CommonModule, FormsModule],
  styleUrl: './vouchers-explorer.css',
  templateUrl: './vouchers-explorer.html',
})
export class VouchersExplorer implements OnDestroy {
  readonly tallyService = inject(TallyApiService);
  readonly billService = inject(BillService);
  readonly voucherUiUtils = inject(VoucherUiUtilsService);
  private readonly sanitizer = inject(DomSanitizer);
  readonly pdfFrame = viewChild<ElementRef<HTMLIFrameElement>>('pdfFrame');

  readonly pdfPreviewUrl = signal<SafeResourceUrl | null>(null);
  readonly pdfPreviewTitle = signal('');
  readonly pdfPreviewFilename = signal('');
  private pdfObjectUrl: string | null = null;

  // Modal / drawer state
  readonly generatingPdf = signal<{ action: PdfAction; voucher: VoucherItem } | null>(null);
  readonly isGeneratingPdf = computed(() => this.generatingPdf() !== null);
  selectedVoucher = signal<VoucherItem | null>(null);

  // Filters & sorters
  voucherSearch = signal<string>('');
  filterDatePreset = signal<DatePreset>('all');
  filterFromDate = signal<string>('');
  filterToDate = signal<string>('');
  sortField = signal<VoucherSortField>('date');
  sortOrder = signal<SortOrder>('desc');

  // Pagination
  pageSize = signal<number>(25);
  currentPage = signal<number>(1);

  // Summary computeds
  readonly distinctPartiesCount = computed(() => {
    const list = this.tallyService.vouchers();
    const set = new Set<string>();
    list.forEach(v => set.add(this.getPartyDisplayName(v).toLowerCase()));
    return set.size;
  });

  readonly vehiclesCount = computed(() => {
    return this.tallyService.vouchers().filter(v => this.hasVehicleNumber(v)).length;
  });

  readonly activeFilterCount = computed(() => {
    let count = 0;
    if (this.voucherSearch().trim()) count++;
    if (this.filterDatePreset() !== 'all') count++;
    return count;
  });

  readonly filteredVouchers = computed(() => {
    let list = this.tallyService.vouchers();

    const query = this.voucherSearch().toLowerCase().trim();
    if (query) {
      list = list.filter(v => {
        const pName = this.getPartyDisplayName(v).toLowerCase();
        const vNum = (v.voucher_number || '').toLowerCase();
        const vehNo = (v.vehicle_number || '').toLowerCase();
        const guid = (v.guid || '').toLowerCase();
        const st = (v.party?.state || '').toLowerCase();
        const gstin = (v.party?.gstin || '').toLowerCase();
        const narration = (v.narration || '').toLowerCase();
        const itemsMatch = this.getVoucherItems(v).some(i => (i.item_name || '').toLowerCase().includes(query));

        return (
          vNum.includes(query) ||
          pName.includes(query) ||
          vehNo.includes(query) ||
          guid.includes(query) ||
          st.includes(query) ||
          gstin.includes(query) ||
          narration.includes(query) ||
          itemsMatch
        );
      });
    }

    const preset = this.filterDatePreset();
    if (preset !== 'all') {
      const from = this.filterFromDate();
      const to = this.filterToDate();

      list = list.filter(v => {
        const vDate = normalizeDateStr(v.date);
        if (!vDate) return true;
        if (from && vDate < from) return false;
        if (to && vDate > to) return false;
        return true;
      });
    }

    const field = this.sortField();
    const order = this.sortOrder();

    return [...list].sort((a, b) => {
      let cmp = 0;
      if (field === 'date') {
        const da = normalizeDateStr(a.date);
        const db = normalizeDateStr(b.date);
        cmp = da.localeCompare(db);
        if (cmp === 0) {
          cmp = (a.voucher_number || '').localeCompare(b.voucher_number || '', undefined, {
            numeric: true,
            sensitivity: 'base'
          });
        }
      } else if (field === 'voucher_number') {
        cmp = (a.voucher_number || '').localeCompare(b.voucher_number || '', undefined, {
          numeric: true,
          sensitivity: 'base'
        });
      } else if (field === 'party') {
        const pa = this.getPartyDisplayName(a).toLowerCase();
        const pb = this.getPartyDisplayName(b).toLowerCase();
        cmp = pa.localeCompare(pb);
      } else if (field === 'amount') {
        cmp = this.getVoucherTotal(a) - this.getVoucherTotal(b);
      } else if (field === 'items') {
        cmp = this.getVoucherItems(a).length - this.getVoucherItems(b).length;
      }

      return order === 'asc' ? cmp : -cmp;
    });
  });

  readonly totalVouchersAmount = computed(() => {
    return this.filteredVouchers().reduce((acc, v) => acc + this.getVoucherTotal(v), 0);
  });

  readonly averageVoucherAmount = computed(() => {
    const list = this.filteredVouchers();
    if (list.length === 0) return 0;
    return this.totalVouchersAmount() / list.length;
  });

  readonly totalPages = computed(() => {
    const sz = this.pageSize();
    if (sz <= 0) return 1;
    return Math.max(1, Math.ceil(this.filteredVouchers().length / sz));
  });

  readonly paginatedVouchers = computed(() => {
    const list = this.filteredVouchers();
    const sz = this.pageSize();
    if (sz <= 0) return list;
    const page = Math.min(Math.max(1, this.currentPage()), this.totalPages());
    const start = (page - 1) * sz;
    return list.slice(start, start + sz);
  });

  setSort(field: VoucherSortField): void {
    if (this.sortField() === field) {
      this.sortOrder.update(o => (o === 'asc' ? 'desc' : 'asc'));
    } else {
      this.sortField.set(field);
      if (field === 'date' || field === 'amount' || field === 'items') {
        this.sortOrder.set('desc');
      } else {
        this.sortOrder.set('asc');
      }
    }
    this.currentPage.set(1);
  }

  setDateFilterPreset(preset: DatePreset): void {
    this.filterDatePreset.set(preset);

    if (preset !== 'custom') {
      const { from, to } = this.voucherUiUtils.computeDateRange(preset);
      this.filterFromDate.set(from);
      this.filterToDate.set(to);
    }
    this.currentPage.set(1);
  }

  resetAllFilters(): void {
    this.voucherSearch.set('');
    this.filterDatePreset.set('all');
    this.filterFromDate.set('');
    this.filterToDate.set('');
    this.currentPage.set(1);
  }

  goToPage(p: number): void {
    const page = Math.min(Math.max(1, p), this.totalPages());
    this.currentPage.set(page);
  }

  nextPage(): void {
    if (this.currentPage() < this.totalPages()) {
      this.currentPage.update(p => p + 1);
    }
  }

  prevPage(): void {
    if (this.currentPage() > 1) {
      this.currentPage.update(p => p - 1);
    }
  }

  setPageSize(size: number): void {
    this.pageSize.set(size);
    this.currentPage.set(1);
  }

  copyVoucherNumber(vNum: string): void {
    if (!vNum) return;
    navigator.clipboard.writeText(vNum).then(() => {
      this.tallyService.activeActionMessage.set(`Voucher #${vNum} copied to clipboard!`);
      setTimeout(() => this.tallyService.clearActionMessage(), 2500);
    });
  }

  triggerTallyScan(): void {
    this.voucherUiUtils.triggerTallyScan();
  }

  retryTallyConnection(): void {
    this.tallyService.clearError();
    this.tallyService.refreshActiveCompany().subscribe();
  }

  openVoucherDetail(voucher: VoucherItem): void {
    this.selectedVoucher.set(voucher);
  }

  closeVoucherDetail(): void {
    this.selectedVoucher.set(null);
  }

  @HostListener('document:keydown.escape')
  closeVoucherDetailOnEscape(): void {
    if (this.pdfPreviewUrl()) this.closePdfPreview();
    else if (this.selectedVoucher()) this.closeVoucherDetail();
  }

  closePdfPreview(): void {
    this.pdfPreviewUrl.set(null);
    this.pdfPreviewTitle.set('');
    this.pdfPreviewFilename.set('');
    if (this.pdfObjectUrl) URL.revokeObjectURL(this.pdfObjectUrl);
    this.pdfObjectUrl = null;
  }

  downloadPdfPreview(): void {
    if (!this.pdfObjectUrl || !this.pdfPreviewFilename()) return;

    const link = document.createElement('a');
    link.href = this.pdfObjectUrl;
    link.download = this.pdfPreviewFilename();
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  printPdfPreview(): void {
    this.pdfFrame()?.nativeElement.contentWindow?.print();
  }

  ngOnDestroy(): void {
    this.closePdfPreview();
  }

  private showPdfPreview(blob: Blob, title: string, filename: string): void {
    this.closePdfPreview();
    this.pdfObjectUrl = URL.createObjectURL(blob);
    this.pdfPreviewUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(this.pdfObjectUrl));
    this.pdfPreviewTitle.set(title);
    this.pdfPreviewFilename.set(filename);
  }

  getVoucherTotal(voucher: VoucherItem): number {
    if (voucher.total_amount !== undefined && voucher.total_amount !== null && voucher.total_amount > 0) {
      return voucher.total_amount;
    }
    const items = this.getVoucherItems(voucher);
    if (items.length > 0) {
      return items.reduce((acc, item) => acc + (Number(item.amount) || 0), 0);
    }
    if (voucher.ledger_entries && voucher.ledger_entries.length > 0) {
      return voucher.ledger_entries.reduce((acc, item) => acc + Math.abs(Number(item.amount) || 0), 0);
    }
    return 0;
  }

  getPartyDisplayName(voucher: VoucherItem): string {
    return voucher.party?.name || voucher.party?.ledger_name || 'N/A';
  }

  getVoucherItems(voucher: VoucherItem) {
    return voucher.inventory_entries || [];
  }

  hasVehicleNumber(voucher: VoucherItem): boolean {
    const vehicleNumber = (voucher.vehicle_number || '').trim();
    return Boolean(vehicleNumber && !['—', '-', 'N/A', 'NA'].includes(vehicleNumber.toUpperCase()));
  }

  isGeneratingPdfFor(action: PdfAction, voucher: VoucherItem): boolean {
    const current = this.generatingPdf();
    return current?.action === action && current.voucher === voucher;
  }

  private readonly ERROR_MESSAGES = {
    invoiceView: 'Could not render PDF invoice',
    invoiceDownload: 'Could not generate PDF invoice',
    deliveryNoteView: 'Could not render Delivery Note',
    deliveryNoteDownload: 'Could not generate Delivery Note PDF',
  };

  async viewVoucherPdf(voucher: VoucherItem): Promise<void> {
    try {
      this.generatingPdf.set({ action: 'view-invoice', voucher });
      const sale = mapVoucherToSaleRecord(voucher);
      const blob = await this.billService.generateInvoicePdf(sale);
      this.showPdfPreview(
        blob,
        `Invoice #${voucher.voucher_number || ''}`,
        `invoice-${voucher.voucher_number || 'invoice'}.pdf`,
      );
    } catch (err: any) {
      this.handlePdfError(err, 'invoiceView', 'view-invoice', voucher);
    } finally {
      this.generatingPdf.set(null);
    }
  }

  async downloadVoucherPdf(voucher: VoucherItem): Promise<void> {
    try {
      this.generatingPdf.set({ action: 'download-invoice', voucher });
      const sale = mapVoucherToSaleRecord(voucher);
      await this.billService.downloadPdf(sale);
    } catch (err: any) {
      this.handlePdfError(err, 'invoiceDownload', 'download-invoice', voucher);
    } finally {
      this.generatingPdf.set(null);
    }
  }

  async viewVoucherDeliveryNote(voucher: VoucherItem): Promise<void> {
    try {
      this.generatingPdf.set({ action: 'view-delivery-note', voucher });
      const sale = mapVoucherToSaleRecord(voucher);
      const blob = await this.billService.generateDeliveryNotePdf(sale);
      this.showPdfPreview(
        blob,
        `Delivery note #${voucher.voucher_number || ''}`,
        `delivery-note-${voucher.voucher_number || 'challan'}.pdf`,
      );
    } catch (err: any) {
      this.handlePdfError(err, 'deliveryNoteView', 'view-delivery-note', voucher);
    } finally {
      this.generatingPdf.set(null);
    }
  }

  async downloadVoucherDeliveryNote(voucher: VoucherItem): Promise<void> {
    try {
      this.generatingPdf.set({ action: 'download-delivery-note', voucher });
      const sale = mapVoucherToSaleRecord(voucher);
      await this.billService.downloadDeliveryNotePdf(sale);
    } catch (err: any) {
      this.handlePdfError(err, 'deliveryNoteDownload', 'download-delivery-note', voucher);
    } finally {
      this.generatingPdf.set(null);
    }
  }

  private handlePdfError(err: any, errorKey: keyof typeof this.ERROR_MESSAGES, action: PdfAction, voucher: VoucherItem): void {
    const errorMessage = this.ERROR_MESSAGES[errorKey];
    const details = err?.message || String(err);

    console.error(`Failed to ${action} for voucher ${voucher.voucher_number}:`, details);

    // Determine error category for user-friendly messaging
    let userMessage = errorMessage;

    if (details.includes('network') || details.includes('offline')) {
      userMessage = `${errorMessage} - Please check your internet connection and try again.`;
    } else if (details.includes('PDF') || details.includes('font') || details.includes('Lexend')) {
      userMessage = `${errorMessage} - There might be a problem with the PDF template or font files.`;
    } else if (details.includes('logo') || details.includes('image')) {
      userMessage = `${errorMessage} - The company logo failed to load but the PDF should still be usable.`;
    } else {
      userMessage = `${errorMessage}: ${details}`;
    }

    alert(userMessage);
  }
}
