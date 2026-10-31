import { Injectable, inject } from '@angular/core';
import { TallyApiService } from './tally-api.service';

export type DatePreset = 'all' | 'today' | 'yesterday' | 'week' | 'month' | 'fy' | 'custom';

@Injectable({ providedIn: 'root' })
export class VoucherUiUtilsService {
  private readonly tallyService = inject(TallyApiService);

  computeDateRange(preset: Exclude<DatePreset, 'custom'>): { from: string; to: string } {
    const today = new Date();
    const formatDate = (date: Date) => date.toISOString().slice(0, 10);

    if (preset === 'all') return { from: '', to: '' };
    if (preset === 'today') {
      const value = formatDate(today);
      return { from: value, to: value };
    }
    if (preset === 'yesterday') {
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      const value = formatDate(yesterday);
      return { from: value, to: value };
    }
    if (preset === 'week') {
      const past = new Date();
      past.setDate(past.getDate() - 7);
      return { from: formatDate(past), to: formatDate(today) };
    }
    if (preset === 'month') {
      return { from: formatDate(new Date(today.getFullYear(), today.getMonth(), 1)), to: formatDate(today) };
    }
    const year = today.getMonth() < 3 ? today.getFullYear() - 1 : today.getFullYear();
    return { from: `${year}-04-01`, to: formatDate(today) };
  }

  triggerTallyScan(): void {
    this.tallyService.clearError();
    this.tallyService.activeActionMessage.set('Loading vouchers directly from Tally Prime...');
    this.tallyService.fetchVouchers().subscribe(vouchers => {
      this.tallyService.activeActionMessage.set(vouchers === null || this.tallyService.errorMessage()
        ? 'Could not load vouchers from Tally Prime. Check the error message and try again.'
        : `Loaded ${vouchers.length} voucher(s) directly from Tally Prime.`);
      setTimeout(() => this.tallyService.clearActionMessage(), 4500);
    });
  }
}
