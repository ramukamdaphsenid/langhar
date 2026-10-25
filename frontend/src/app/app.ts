import { Component, ViewEncapsulation, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { SyncApiService } from './services/sync-api.service';
import { SyncUiUtilsService } from './services/sync-ui-utils.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.html',
  styleUrl: './app.css',
  encapsulation: ViewEncapsulation.None
})
export class App {
  readonly syncService = inject(SyncApiService);
  readonly syncUiUtils = inject(SyncUiUtilsService);

  // Integration Connection Health (delegated to SyncUiUtilsService)
  readonly isTallyConnected = this.syncUiUtils.isTallyConnected;
  readonly isFirebaseConnected = this.syncUiUtils.isFirebaseConnected;
  readonly headerStatus = computed(() => {
    if (this.syncService.isCheckingHealth()) {
      return { label: 'Checking systems', tone: 'warning' as const };
    }
    if (this.syncService.isSyncing()) {
      return { label: 'Sync in progress', tone: 'syncing' as const };
    }
    if (!this.syncService.isBackendOnline()) {
      return { label: 'Backend offline', tone: 'offline' as const };
    }

    const tallyConnected = this.isTallyConnected();
    const firebaseConnected = this.isFirebaseConnected();
    if (tallyConnected && firebaseConnected) {
      return { label: 'Systems operational', tone: 'online' as const };
    }
    if (tallyConnected || firebaseConnected) {
      return { label: 'Partial connection', tone: 'warning' as const };
    }
    return { label: 'Needs attention', tone: 'warning' as const };
  });

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

  constructor() {
    this.initTheme();
  }
}
