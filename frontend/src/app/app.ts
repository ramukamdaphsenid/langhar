import { Component, OnInit, OnDestroy, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SyncApiService } from './services/sync-api.service';
import { LogEntry, VoucherItem } from './models/sync.models';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App implements OnInit, OnDestroy {
  readonly syncService = inject(SyncApiService);

  // Theme Management (Light / Dark)
  isDarkMode = signal<boolean>(true);

  private initTheme(): void {
    const saved = typeof localStorage !== 'undefined' ? localStorage.getItem('langhar_theme') : null;
    const isLight = saved === 'light';
    this.setTheme(!isLight);
  }

  toggleTheme(): void {
    this.setTheme(!this.isDarkMode());
  }

  setTheme(dark: boolean): void {
    this.isDarkMode.set(dark);
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('langhar_theme', dark ? 'dark' : 'light');
    }
    if (typeof document !== 'undefined') {
      if (dark) {
        document.body.classList.remove('light-theme');
        document.body.classList.add('dark-theme');
      } else {
        document.body.classList.remove('dark-theme');
        document.body.classList.add('light-theme');
      }
    }
  }

  // Active navigation tab
  activeTab = signal<'vouchers' | 'logs' | 'diagnostics'>('vouchers');

  // Modal / Drawer state
  isDateRangeModalOpen = signal<boolean>(false);
  isSettingsModalOpen = signal<boolean>(false);
  isResetConfirmOpen = signal<boolean>(false);
  selectedVoucher = signal<VoucherItem | null>(null);

  // Date Range Sync Form
  fromDate = signal<string>('');
  toDate = signal<string>('');
  dateRangeFull = signal<boolean>(false);

  // Daemon settings
  daemonIntervalInput = signal<number>(60);

  // Voucher explorer filters
  voucherSearch = signal<string>('');

  // Logs filters
  logLevelFilter = signal<string>('ALL');
  logSearch = signal<string>('');
  logAutoScroll = signal<boolean>(true);

  // Settings form
  apiUrlInput = signal<string>('');

  // Local ticker for smooth countdown
  countdownSeconds = signal<number | null>(null);
  private tickerInterval: any = null;

  // Filtered vouchers computed
  readonly filteredVouchers = computed(() => {
    const list = this.syncService.vouchers();
    const query = this.voucherSearch().toLowerCase().trim();
    if (!query) return list;
    return list.filter(v => {
      const pName = this.getPartyDisplayName(v).toLowerCase();
      const vNum = (v.voucher_number || '').toLowerCase();
      const vehNo = (v.vehicle_number || '').toLowerCase();
      const guid = (v.guid || '').toLowerCase();
      const st = (v.state_name || v.party?.state || '').toLowerCase();
      const gstin = (v.party_gstin || v.party?.gstin || '').toLowerCase();
      return (
        vNum.includes(query) ||
        pName.includes(query) ||
        vehNo.includes(query) ||
        guid.includes(query) ||
        st.includes(query) ||
        gstin.includes(query)
      );
    });
  });

  // Filtered logs computed
  readonly filteredLogs = computed(() => {
    const list = this.syncService.logs();
    const level = this.logLevelFilter();
    const search = this.logSearch().toLowerCase().trim();

    return list.filter(l => {
      const matchLevel = level === 'ALL' || l.level.toUpperCase() === level;
      const matchSearch = !search ||
        l.message.toLowerCase().includes(search) ||
        l.timestamp.toLowerCase().includes(search);
      return matchLevel && matchSearch;
    });
  });

  ngOnInit(): void {
    this.initTheme();
    const current = this.syncService.apiBaseUrl();
    this.apiUrlInput.set(current || 'http://localhost:8000');

    // Listen for daemon countdown sync
    this.tickerInterval = setInterval(() => {
      const daemon = this.syncService.status()?.daemon;
      if (daemon?.is_running && daemon?.next_countdown_seconds !== undefined) {
        if (this.countdownSeconds() === null || this.countdownSeconds()! <= 0) {
          this.countdownSeconds.set(daemon.next_countdown_seconds);
        } else {
          this.countdownSeconds.update(v => (v && v > 0 ? v - 1 : 0));
        }
      } else {
        this.countdownSeconds.set(null);
      }
    }, 1000);
  }

  ngOnDestroy(): void {
    if (this.tickerInterval) {
      clearInterval(this.tickerInterval);
    }
  }

  // --- Sync Trigger Handlers ---

  triggerQuickSync(): void {
    if (this.syncService.isSyncing()) return;
    this.syncService.triggerSync({ full: false }).subscribe({
      next: () => {},
      error: () => {}
    });
  }

  triggerFullSync(): void {
    if (this.syncService.isSyncing()) return;
    if (confirm('A Full Resync will re-evaluate and sync all vouchers regardless of the current AlterID. Proceed?')) {
      this.syncService.triggerSync({ full: true }).subscribe({
        next: () => {},
        error: () => {}
      });
    }
  }

  openDateRangeModal(): void {
    // Default fromDate to 7 days ago, toDate to today
    const now = new Date();
    const past = new Date();
    past.setDate(past.getDate() - 7);

    this.toDate.set(now.toISOString().slice(0, 10));
    this.fromDate.set(past.toISOString().slice(0, 10));
    this.dateRangeFull.set(false);
    this.isDateRangeModalOpen.set(true);
  }

  setDatePreset(preset: 'today' | 'yesterday' | 'week' | 'month' | 'fy'): void {
    const today = new Date();
    const formatDate = (d: Date) => d.toISOString().slice(0, 10);

    if (preset === 'today') {
      const t = formatDate(today);
      this.fromDate.set(t);
      this.toDate.set(t);
    } else if (preset === 'yesterday') {
      const y = new Date();
      y.setDate(y.getDate() - 1);
      const str = formatDate(y);
      this.fromDate.set(str);
      this.toDate.set(str);
    } else if (preset === 'week') {
      const past = new Date();
      past.setDate(past.getDate() - 7);
      this.fromDate.set(formatDate(past));
      this.toDate.set(formatDate(today));
    } else if (preset === 'month') {
      const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
      this.fromDate.set(formatDate(startOfMonth));
      this.toDate.set(formatDate(today));
    } else if (preset === 'fy') {
      // Indian Financial Year: Apr 1 - Mar 31
      const year = today.getMonth() < 3 ? today.getFullYear() - 1 : today.getFullYear();
      this.fromDate.set(`${year}-04-01`);
      this.toDate.set(formatDate(today));
    }
  }

  submitDateRangeSync(): void {
    const from_date = this.fromDate().trim() || undefined;
    const to_date = this.toDate().trim() || undefined;
    const full = this.dateRangeFull();

    this.isDateRangeModalOpen.set(false);
    this.syncService.triggerSync({ from_date, to_date, full }).subscribe();
  }

  // --- Daemon Controls ---

  toggleDaemon(): void {
    const daemon = this.syncService.status()?.daemon;
    if (daemon?.is_running) {
      this.syncService.stopDaemon().subscribe();
    } else {
      this.syncService.startDaemon(this.daemonIntervalInput()).subscribe();
    }
  }

  // --- Reset State ---

  openResetModal(): void {
    this.isResetConfirmOpen.set(true);
  }

  confirmReset(): void {
    this.isResetConfirmOpen.set(false);
    this.syncService.resetState().subscribe();
  }

  // --- Voucher details modal ---

  openVoucherDetail(voucher: VoucherItem): void {
    this.selectedVoucher.set(voucher);
  }

  closeVoucherDetail(): void {
    this.selectedVoucher.set(null);
  }

  // --- Settings ---

  saveSettings(): void {
    this.syncService.setBaseUrl(this.apiUrlInput());
    this.isSettingsModalOpen.set(false);
  }

  copyLogsToClipboard(): void {
    const logs = this.filteredLogs();
    const text = logs.map(l => `[${l.timestamp}] [${l.level}] ${l.message}`).join('\n');
    navigator.clipboard.writeText(text).then(() => {
      this.syncService.activeActionMessage.set('Logs copied to clipboard!');
      setTimeout(() => this.syncService.clearActionMessage(), 3000);
    });
  }

  // Calculate voucher total sum from line items if total_amount is not set
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
}
