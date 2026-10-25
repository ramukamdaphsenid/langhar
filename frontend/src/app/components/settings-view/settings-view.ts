import { Component, OnInit, OnDestroy, inject, signal, effect, untracked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { SyncApiService } from '../../services/sync-api.service';
import { SyncUiUtilsService, DatePreset } from '../../services/sync-ui-utils.service';
import { BillService } from '../../services/bill.service';
import { CompanyProfile, DEFAULT_COMPANY_PROFILE } from '../../models/company.model';

@Component({
  selector: 'app-settings-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './settings-view.html',
  styleUrl: './settings-view.css'
})
export class SettingsView implements OnInit, OnDestroy {
  readonly syncService = inject(SyncApiService);
  readonly billService = inject(BillService);
  readonly syncUiUtils = inject(SyncUiUtilsService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  // Active settings tab, driven by route query param (?tab=invoice|?tab=sync)
  settingsTab = signal<'invoice' | 'sync'>('invoice');

  // Company Profile & Invoice Customization Form State
  companyProfileForm = signal<CompanyProfile>({ ...DEFAULT_COMPANY_PROFILE });
  isSavingCompanyProfile = signal<boolean>(false);
  isLoadingCompanyProfile = signal<boolean>(false);
  companySaveSuccess = signal<boolean>(false);
  companySaveError = signal<string | null>(null);

  // Connection health (delegated to SyncUiUtilsService)
  readonly isTallyConnected = this.syncUiUtils.isTallyConnected;

  // Modal state
  isGeneratingPdf = signal<boolean>(false);
  generatingPdfMessage = signal<string>('Preparing document...');
  isDateRangeModalOpen = signal<boolean>(false);
  isResetConfirmOpen = signal<boolean>(false);
  isClearFirestoreConfirmOpen = signal<boolean>(false);
  isClearingFirestore = signal<boolean>(false);
  isCleaningDuplicates = signal<boolean>(false);

  // Date Range Sync Form
  fromDate = signal<string>('');
  toDate = signal<string>('');
  dateRangeFull = signal<boolean>(false);

  // Local ticker for smooth countdown
  countdownSeconds = signal<number | null>(null);
  private tickerInterval: any = null;

  constructor() {
    effect(() => {
      const tab = this.settingsTab();
      untracked(() => {
        if (tab === 'invoice') {
          this.loadCompanyProfile();
        }
      });
    });
  }

  ngOnInit(): void {
    this.companyProfileForm.set(this.billService.getConfig());

    // Sync settingsTab signal with route query param
    const initialTab = this.route.snapshot.queryParamMap.get('tab');
    this.settingsTab.set(initialTab === 'sync' ? 'sync' : 'invoice');

    this.route.queryParams.subscribe(params => {
      this.settingsTab.set(params['tab'] === 'sync' ? 'sync' : 'invoice');
    });

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

  openSettings(tab: 'invoice' | 'sync' = 'invoice'): void {
    this.router.navigate(['/settings'], { queryParams: { tab } });
  }

  loadCompanyProfile(notify = false): void {
    this.isLoadingCompanyProfile.set(true);
    this.syncService.fetchCompanyProfile().subscribe({
      next: (profile) => {
        this.isLoadingCompanyProfile.set(false);
        if (profile && profile.company_name) {
          this.billService.setCompanyProfile(profile, true);
          this.companyProfileForm.set(this.billService.getConfig());
          if (notify) {
            this.syncService.activeActionMessage.set('Company Profile & Invoice Details reloaded from Cloud Firestore!');
            setTimeout(() => this.syncService.clearActionMessage(), 3500);
          }
        }
      },
      error: (err) => {
        this.isLoadingCompanyProfile.set(false);
        if (notify) {
          const msg = err?.error?.detail || err?.message || 'Failed to reload profile from server';
          this.syncService.errorMessage.set(msg);
          setTimeout(() => this.syncService.clearError(), 4000);
        }
      }
    });
  }

  updateCompanyField<K extends keyof CompanyProfile>(field: K, value: any): void {
    this.companyProfileForm.update(prev => ({
      ...prev,
      [field]: value
    }));
  }

  saveCompanyProfile(): void {
    this.isSavingCompanyProfile.set(true);
    this.companySaveSuccess.set(false);
    this.companySaveError.set(null);

    const profile = this.companyProfileForm();
    this.billService.setCompanyProfile(profile, true);

    this.syncService.saveCompanyProfile(profile).subscribe({
      next: (res: any) => {
        this.isSavingCompanyProfile.set(false);
        const savedProfile = res?.profile || profile;
        this.billService.setCompanyProfile(savedProfile, true);
        this.companyProfileForm.set(this.billService.getConfig());

        if (res && res.status === 'PARTIAL_SUCCESS') {
          this.companySaveSuccess.set(true);
          const warnMsg = res.message || 'Saved locally in server cache. Warning: Failed to write to Firebase Firestore.';
          this.companySaveError.set(warnMsg);
          this.syncService.errorMessage.set(warnMsg);
          this.syncService.activeActionMessage.set('Saved in local cache. Firestore sync warning.');
        } else {
          this.companySaveSuccess.set(true);
          this.companySaveError.set(null);
          this.syncService.activeActionMessage.set('Company details & invoice settings saved and synced to Firebase Firestore!');
        }
        setTimeout(() => {
          this.companySaveSuccess.set(false);
          this.syncService.clearActionMessage();
        }, 4000);
      },
      error: (err: any) => {
        this.isSavingCompanyProfile.set(false);
        this.companySaveSuccess.set(false);
        const errMsg = err?.error?.detail || err?.message || 'Failed to save company profile';
        this.companySaveError.set(errMsg);
        this.syncService.errorMessage.set(errMsg);
        this.syncService.activeActionMessage.set(`Failed to save company profile: ${errMsg}`);
        setTimeout(() => {
          this.syncService.clearActionMessage();
        }, 5000);
      }
    });
  }

  async previewSampleInvoicePdf(): Promise<void> {
    try {
      this.generatingPdfMessage.set('Rendering sample invoice PDF...');
      this.isGeneratingPdf.set(true);
      this.billService.setCompanyProfile(this.companyProfileForm());
      const sample = this.billService.getSampleSaleRecord();
      await this.billService.openPdf(sample);
    } catch (err: any) {
      console.error('Failed to preview PDF:', err);
      alert('Could not render PDF invoice: ' + (err?.message || err));
    } finally {
      this.isGeneratingPdf.set(false);
    }
  }

  async previewSampleDeliveryNotePdf(): Promise<void> {
    try {
      this.generatingPdfMessage.set('Rendering sample delivery note...');
      this.isGeneratingPdf.set(true);
      this.billService.setCompanyProfile(this.companyProfileForm());
      const sample = this.billService.getSampleSaleRecord();
      await this.billService.openDeliveryNotePdf(sample);
    } catch (err: any) {
      console.error('Failed to preview Delivery Note:', err);
      alert('Could not render Delivery Note: ' + (err?.message || err));
    } finally {
      this.isGeneratingPdf.set(false);
    }
  }

  testTally(): void {
    this.syncService.testTally().subscribe();
  }

  testFirebase(): void {
    this.syncService.testFirebase().subscribe();
  }

  triggerTallyScan(sourcePref?: 'live' | 'firestore' | 'auto'): void {
    this.syncUiUtils.triggerTallyScan(sourcePref);
  }

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
    const now = new Date();
    const past = new Date();
    past.setDate(past.getDate() - 7);

    this.toDate.set(now.toISOString().slice(0, 10));
    this.fromDate.set(past.toISOString().slice(0, 10));
    this.dateRangeFull.set(false);
    this.isDateRangeModalOpen.set(true);
  }

  setDatePreset(preset: 'today' | 'yesterday' | 'week' | 'month' | 'fy'): void {
    const { from, to } = this.syncUiUtils.computeDateRange(preset);
    this.fromDate.set(from);
    this.toDate.set(to);
  }

  submitDateRangeSync(): void {
    const from_date = this.fromDate().trim() || undefined;
    const to_date = this.toDate().trim() || undefined;
    const full = this.dateRangeFull();

    this.isDateRangeModalOpen.set(false);
    this.syncService.triggerSync({ from_date, to_date, full }).subscribe();
  }

  toggleDaemon(): void {
    const daemon = this.syncService.status()?.daemon;
    if (daemon?.is_running) {
      this.syncService.stopDaemon().subscribe();
    } else {
      this.syncService.startDaemon(/* interval */ 60).subscribe();
    }
  }

  openResetModal(): void {
    this.isResetConfirmOpen.set(true);
  }

  confirmReset(): void {
    this.isResetConfirmOpen.set(false);
    this.syncService.resetState().subscribe();
  }

  openClearFirestoreModal(): void {
    this.isClearFirestoreConfirmOpen.set(true);
  }

  confirmClearFirestore(): void {
    this.isClearingFirestore.set(true);
    this.syncService.clearFirestoreData().subscribe({
      next: () => {
        this.isClearingFirestore.set(false);
        this.isClearFirestoreConfirmOpen.set(false);
        setTimeout(() => this.syncService.clearActionMessage(), 4500);
      },
      error: () => {
        this.isClearingFirestore.set(false);
        this.isClearFirestoreConfirmOpen.set(false);
      }
    });
  }

  triggerCleanupDuplicates(): void {
    if (this.isCleaningDuplicates() || this.syncService.isSyncing()) return;
    this.isCleaningDuplicates.set(true);
    this.syncService.cleanupFirestoreDuplicates().subscribe({
      next: () => {
        this.isCleaningDuplicates.set(false);
        setTimeout(() => this.syncService.clearActionMessage(), 5000);
      },
      error: () => {
        this.isCleaningDuplicates.set(false);
      }
    });
  }

}
