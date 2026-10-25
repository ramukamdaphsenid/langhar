import { Injectable, inject, computed } from '@angular/core';
import { SyncApiService } from './sync-api.service';

export type DatePreset = 'all' | 'today' | 'yesterday' | 'week' | 'month' | 'fy' | 'custom';

@Injectable({ providedIn: 'root' })
export class SyncUiUtilsService {
  private readonly syncService = inject(SyncApiService);

  readonly isTallyConnected = computed<boolean>(() => {
    const diag = this.syncService.diagnostics();
    if (diag?.tally?.ok !== undefined) {
      return diag.tally.ok;
    }
    const st = this.syncService.status();
    return this.syncService.isBackendOnline() && (st?.state?.last_status === 'SUCCESS' || (st?.state?.total_vouchers_synced ?? 0) > 0);
  });

  readonly isFirebaseConnected = computed<boolean>(() => {
    const diag = this.syncService.diagnostics();
    if (diag?.firebase?.ok !== undefined) {
      return diag.firebase.ok;
    }
    const st = this.syncService.status();
    return this.syncService.isBackendOnline() && (st?.config?.credentials_exists ?? false);
  });

  computeDateRange(preset: Exclude<DatePreset, 'custom'>): { from: string; to: string } {
    const today = new Date();
    const formatDate = (d: Date) => d.toISOString().slice(0, 10);

    if (preset === 'all') {
      return { from: '', to: '' };
    }
    if (preset === 'today') {
      const t = formatDate(today);
      return { from: t, to: t };
    }
    if (preset === 'yesterday') {
      const y = new Date();
      y.setDate(y.getDate() - 1);
      const str = formatDate(y);
      return { from: str, to: str };
    }
    if (preset === 'week') {
      const past = new Date();
      past.setDate(past.getDate() - 7);
      return { from: formatDate(past), to: formatDate(today) };
    }
    if (preset === 'month') {
      const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
      return { from: formatDate(startOfMonth), to: formatDate(today) };
    }
    const year = today.getMonth() < 3 ? today.getFullYear() - 1 : today.getFullYear();
    return { from: `${year}-04-01`, to: formatDate(today) };
  }

  triggerTallyScan(sourcePref?: 'live' | 'firestore' | 'auto'): void {
    const isTally = this.isTallyConnected();
    if (sourcePref === 'firestore') {
      this.syncService.activeActionMessage.set('Loading sales vouchers directly from Firebase Firestore...');
    } else if (!isTally) {
      this.syncService.activeActionMessage.set('Tally Prime is disconnected. Automatically loading sales vouchers from Firebase Firestore...');
    } else {
      this.syncService.activeActionMessage.set('Scanning local Tally Prime for sales vouchers...');
    }

    this.syncService.fetchVouchers(undefined, '', sourcePref).subscribe({
      next: (vouchers) => {
        const src = this.syncService.vouchersSource();
        if (src === 'firestore') {
          this.syncService.activeActionMessage.set(
            `Loaded ${vouchers.length} vouchers from Firebase Firestore (Tally is disconnected).`
          );
        } else if (src === 'live') {
          this.syncService.activeActionMessage.set(
            `Live scan complete: Loaded ${vouchers.length} vouchers from Tally Prime.`
          );
        } else {
          this.syncService.activeActionMessage.set(
            `Loaded ${vouchers.length} vouchers from XML test dataset.`
          );
        }
        setTimeout(() => this.syncService.clearActionMessage(), 4500);
      },
      error: () => {
        this.syncService.errorMessage.set('Could not fetch sales vouchers.');
      }
    });
  }
}
