import { Component, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SyncApiService } from '../../services/sync-api.service';
import { SyncUiUtilsService, DatePreset } from '../../services/sync-ui-utils.service';
import { BillService } from '../../services/bill.service';
import { VoucherItem } from '../../models/sync.models';
import { mapVoucherToSaleRecord, ALLOWED_VOUCHER_TYPES } from '../../services/bill.mapper';

export type VoucherSortField = 'date' | 'voucher_number' | 'party' | 'amount' | 'items';
export type SortOrder = 'asc' | 'desc';

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
  templateUrl: './vouchers-explorer.html',
  styleUrl: './vouchers-explorer.css'
})
export class VouchersExplorer {
  readonly syncService = inject(SyncApiService);
  readonly billService = inject(BillService);
  readonly syncUiUtils = inject(SyncUiUtilsService);

  // Connection health (delegated to SyncUiUtilsService)
  readonly isTallyConnected = this.syncUiUtils.isTallyConnected;

  // Modal / drawer state
  isGeneratingPdf = signal<boolean>(false);
  generatingPdfMessage = signal<string>('Preparing document...');
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
    const list = this.syncService.vouchers();
    const set = new Set<string>();
    list.forEach(v => set.add(this.getPartyDisplayName(v).toLowerCase()));
    return set.size;
  });

  readonly vehiclesCount = computed(() => {
    return this.syncService.vouchers().filter(v => this.hasVehicleNumber(v)).length;
  });

  readonly activeFilterCount = computed(() => {
    let count = 0;
    if (this.voucherSearch().trim()) count++;
    if (this.filterDatePreset() !== 'all') count++;
    return count;
  });

  readonly filteredVouchers = computed(() => {
    let list = this.syncService.vouchers();

    list = list.filter(v => ALLOWED_VOUCHER_TYPES.has((v.voucher_type || '').trim().toUpperCase()));

    const query = this.voucherSearch().toLowerCase().trim();
    if (query) {
      list = list.filter(v => {
        const pName = this.getPartyDisplayName(v).toLowerCase();
        const vNum = (v.voucher_number || '').toLowerCase();
        const vehNo = (v.vehicle_number || '').toLowerCase();
        const guid = (v.guid || '').toLowerCase();
        const st = (v.state_name || v.party?.state || '').toLowerCase();
        const gstin = (v.party_gstin || v.party?.gstin || '').toLowerCase();
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
      const { from, to } = this.syncUiUtils.computeDateRange(preset);
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

  exportFilteredToCsv(): void {
    const items = this.filteredVouchers();
    if (items.length === 0) {
      this.syncService.errorMessage.set('No vouchers available to export for current filter criteria.');
      return;
    }

    const headers = [
      'Voucher Number',
      'Date',
      'Voucher Type',
      'Party Name',
      'Party Ledger',
      'Vehicle Number',
      'State',
      'GSTIN',
      'Items Count',
      'Total Amount (INR)',
      'GUID'
    ];

    const escapeCsv = (val: any) => {
      const s = String(val ?? '').replace(/"/g, '""');
      return `"${s}"`;
    };

    const rows = items.map(v => [
      escapeCsv(v.voucher_number),
      escapeCsv(v.date),
      escapeCsv(v.voucher_type || 'Sales'),
      escapeCsv(this.getPartyDisplayName(v)),
      escapeCsv(v.party_ledger_name || ''),
      escapeCsv(v.vehicle_number || ''),
      escapeCsv(v.state_name || v.party?.state || ''),
      escapeCsv(v.party_gstin || v.party?.gstin || ''),
      escapeCsv(this.getVoucherItems(v).length),
      escapeCsv(this.getVoucherTotal(v).toFixed(2)),
      escapeCsv(v.guid || '')
    ].join(','));

    const csvContent = '\uFEFF' + [headers.join(','), ...rows].join('\r\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `langhar_vouchers_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    this.syncService.activeActionMessage.set(`Successfully exported ${items.length} vouchers to CSV.`);
    setTimeout(() => this.syncService.clearActionMessage(), 3500);
  }

  copyVoucherNumber(vNum: string): void {
    if (!vNum) return;
    navigator.clipboard.writeText(vNum).then(() => {
      this.syncService.activeActionMessage.set(`Voucher #${vNum} copied to clipboard!`);
      setTimeout(() => this.syncService.clearActionMessage(), 2500);
    });
  }

  triggerTallyScan(sourcePref?: 'live' | 'firestore' | 'auto'): void {
    this.syncUiUtils.triggerTallyScan(sourcePref);
  }

  openVoucherDetail(voucher: VoucherItem): void {
    this.selectedVoucher.set(voucher);
  }

  closeVoucherDetail(): void {
    this.selectedVoucher.set(null);
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
    return voucher.party_name || voucher.party?.name || voucher.party_ledger_name || voucher.party?.ledger_name || 'N/A';
  }

  getVoucherItems(voucher: VoucherItem) {
    return voucher.inventory_entries || voucher.items || [];
  }

  hasVehicleNumber(voucher: VoucherItem): boolean {
    const vehicleNumber = (voucher.vehicle_number || '').trim();
    return Boolean(vehicleNumber && !['—', '-', 'N/A', 'NA'].includes(vehicleNumber.toUpperCase()));
  }

  async viewVoucherPdf(voucher: VoucherItem): Promise<void> {
    try {
      this.generatingPdfMessage.set(`Rendering invoice #${voucher.voucher_number || ''}...`);
      this.isGeneratingPdf.set(true);
      const sale = mapVoucherToSaleRecord(voucher);
      await this.billService.openPdf(sale);
    } catch (err: any) {
      console.error('Failed to view PDF:', err);
      alert('Could not render PDF invoice: ' + (err?.message || err));
    } finally {
      this.isGeneratingPdf.set(false);
    }
  }

  async downloadVoucherPdf(voucher: VoucherItem): Promise<void> {
    try {
      this.generatingPdfMessage.set(`Preparing invoice download for #${voucher.voucher_number || ''}...`);
      this.isGeneratingPdf.set(true);
      const sale = mapVoucherToSaleRecord(voucher);
      await this.billService.downloadPdf(sale);
    } catch (err: any) {
      console.error('Failed to download PDF:', err);
      alert('Could not generate PDF invoice: ' + (err?.message || err));
    } finally {
      this.isGeneratingPdf.set(false);
    }
  }

  async viewVoucherDeliveryNote(voucher: VoucherItem): Promise<void> {
    try {
      this.generatingPdfMessage.set(`Rendering delivery note for #${voucher.voucher_number || ''}...`);
      this.isGeneratingPdf.set(true);
      const sale = mapVoucherToSaleRecord(voucher);
      await this.billService.openDeliveryNotePdf(sale);
    } catch (err: any) {
      console.error('Failed to view Delivery Note:', err);
      alert('Could not render Delivery Note: ' + (err?.message || err));
    } finally {
      this.isGeneratingPdf.set(false);
    }
  }

  async downloadVoucherDeliveryNote(voucher: VoucherItem): Promise<void> {
    try {
      this.generatingPdfMessage.set(`Preparing delivery note download for #${voucher.voucher_number || ''}...`);
      this.isGeneratingPdf.set(true);
      const sale = mapVoucherToSaleRecord(voucher);
      await this.billService.downloadDeliveryNotePdf(sale);
    } catch (err: any) {
      console.error('Failed to download Delivery Note:', err);
      alert('Could not generate Delivery Note PDF: ' + (err?.message || err));
    } finally {
      this.isGeneratingPdf.set(false);
    }
  }
}
