import { Injectable, inject, signal } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, catchError, map, of, tap, throwError } from 'rxjs';
import {
  DiagnosticsResponse,
  LogEntry,
  LogsResponse,
  SyncRequestPayload,
  SyncResult,
  SyncStatusResponse,
  VoucherItem,
  VouchersResponse
} from '../models/sync.models';

@Injectable({
  providedIn: 'root'
})
export class SyncApiService {
  private readonly http = inject(HttpClient);

  // Stored base URL (defaults to http://localhost:8000, or proxy path /api)
  private readonly storageKey = 'tally_sync_api_base_url';
  readonly apiBaseUrl = signal<string>(this.getInitialBaseUrl());

  // Application State Signals
  readonly status = signal<SyncStatusResponse | null>(null);
  readonly diagnostics = signal<DiagnosticsResponse | null>(null);
  readonly logs = signal<LogEntry[]>([]);
  readonly vouchers = signal<VoucherItem[]>([]);
  readonly vouchersSource = signal<'live' | 'mock'>('live');
  readonly isSyncing = signal<boolean>(false);
  readonly isBackendOnline = signal<boolean>(false);
  readonly isCheckingHealth = signal<boolean>(false);
  readonly isTriggeringSync = signal<boolean>(false);
  readonly lastSyncResult = signal<SyncResult | null>(null);
  readonly activeActionMessage = signal<string | null>(null);
  readonly errorMessage = signal<string | null>(null);

  // Auto-refresh config
  readonly autoRefreshEnabled = signal<boolean>(true);
  readonly refreshIntervalSec = signal<number>(4);
  private refreshTimer: any = null;

  constructor() {
    this.startAutoRefresh();
  }

  private getInitialBaseUrl(): string {
    const saved = localStorage.getItem(this.storageKey);
    if (saved) return saved;
    // In browser (container unified port 8000, dev proxy 4200, or custom host), relative URL calls origin
    if (typeof window !== 'undefined') {
      return '';
    }
    return 'http://localhost:8000';
  }

  setBaseUrl(newUrl: string): void {
    const trimmed = newUrl.trim().replace(/\/+$/, '');
    this.apiBaseUrl.set(trimmed);
    localStorage.setItem(this.storageKey, trimmed);
    this.refreshAll();
  }

  private getUrl(endpoint: string): string {
    const base = this.apiBaseUrl();
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    return `${base}${cleanEndpoint}`;
  }

  // --- Core API Calls ---

  fetchStatus(): Observable<SyncStatusResponse | null> {
    return this.http.get<SyncStatusResponse>(this.getUrl('/api/status')).pipe(
      tap((res) => {
        this.status.set(res);
        this.isSyncing.set(res.is_syncing);
        if (res.last_sync_result) {
          this.lastSyncResult.set(res.last_sync_result);
        }
        this.isBackendOnline.set(true);
        this.errorMessage.set(null);
      }),
      catchError((err: HttpErrorResponse) => {
        this.isBackendOnline.set(false);
        return of(null);
      })
    );
  }

  fetchDiagnostics(): Observable<DiagnosticsResponse | null> {
    this.isCheckingHealth.set(true);
    return this.http.get<DiagnosticsResponse>(this.getUrl('/api/check')).pipe(
      tap((res) => {
        this.diagnostics.set(res);
        this.isBackendOnline.set(true);
        this.isCheckingHealth.set(false);
      }),
      catchError((err) => {
        this.isCheckingHealth.set(false);
        return of(null);
      })
    );
  }

  fetchLogs(limit: number = 100): Observable<LogEntry[]> {
    return this.http.get<LogsResponse>(this.getUrl(`/api/logs?limit=${limit}`)).pipe(
      map((res) => res.logs || []),
      tap((logs) => {
        this.logs.set(logs);
      }),
      catchError(() => of([]))
    );
  }

  fetchVouchers(limit: number = 60, search: string = ''): Observable<VoucherItem[]> {
    let url = `/api/vouchers/sample?limit=${limit}`;
    if (search.trim()) {
      url += `&search=${encodeURIComponent(search.trim())}`;
    }
    return this.http.get<VouchersResponse>(this.getUrl(url)).pipe(
      tap((res) => {
        this.vouchers.set(res.vouchers || []);
        this.vouchersSource.set(res.source || 'live');
      }),
      map((res) => res.vouchers || []),
      catchError(() => of([]))
    );
  }

  triggerSync(payload: SyncRequestPayload = {}): Observable<SyncResult> {
    this.isTriggeringSync.set(true);
    this.isSyncing.set(true);
    this.activeActionMessage.set('Triggering synchronization run...');

    return this.http.post<SyncResult>(this.getUrl('/api/sync'), payload).pipe(
      tap((result) => {
        this.lastSyncResult.set(result);
        this.isTriggeringSync.set(false);
        this.isSyncing.set(false);
        this.activeActionMessage.set(
          `Sync ${result.status}: Processed ${result.synced_count ?? 0} voucher(s) in ${result.elapsed_seconds ?? 0}s.`
        );
        this.fetchStatus().subscribe();
        this.fetchLogs().subscribe();
        this.fetchVouchers().subscribe();
      }),
      catchError((err: HttpErrorResponse) => {
        this.isTriggeringSync.set(false);
        this.isSyncing.set(false);
        const detail = err.error?.detail || err.message || 'Synchronization request failed';
        this.errorMessage.set(detail);
        this.activeActionMessage.set(null);
        return throwError(() => new Error(detail));
      })
    );
  }

  startDaemon(interval?: number): Observable<any> {
    this.activeActionMessage.set('Starting background daemon sync...');
    const body = interval ? { interval } : {};
    return this.http.post(this.getUrl('/api/daemon/start'), body).pipe(
      tap(() => {
        this.activeActionMessage.set('Daemon scheduler active.');
        this.fetchStatus().subscribe();
        this.fetchLogs().subscribe();
      }),
      catchError((err) => {
        this.errorMessage.set(err.error?.detail || 'Failed to start daemon');
        return of(null);
      })
    );
  }

  stopDaemon(): Observable<any> {
    this.activeActionMessage.set('Stopping background daemon sync...');
    return this.http.post(this.getUrl('/api/daemon/stop'), {}).pipe(
      tap(() => {
        this.activeActionMessage.set('Daemon scheduler stopped.');
        this.fetchStatus().subscribe();
        this.fetchLogs().subscribe();
      }),
      catchError((err) => {
        this.errorMessage.set(err.error?.detail || 'Failed to stop daemon');
        return of(null);
      })
    );
  }

  resetState(): Observable<any> {
    this.activeActionMessage.set('Resetting sync state AlterID to 0...');
    return this.http.post(this.getUrl('/api/state/reset'), {}).pipe(
      tap(() => {
        this.activeActionMessage.set('State reset. Next sync will perform a full pull.');
        this.fetchStatus().subscribe();
        this.fetchLogs().subscribe();
      }),
      catchError((err) => {
        this.errorMessage.set(err.error?.detail || 'Failed to reset state');
        return of(null);
      })
    );
  }

  // --- Auto Refresh Control ---

  toggleAutoRefresh(enable?: boolean): void {
    const target = enable !== undefined ? enable : !this.autoRefreshEnabled();
    this.autoRefreshEnabled.set(target);
    if (target) {
      this.startAutoRefresh();
    } else {
      this.stopAutoRefresh();
    }
  }

  setRefreshInterval(seconds: number): void {
    this.refreshIntervalSec.set(Math.max(2, seconds));
    if (this.autoRefreshEnabled()) {
      this.stopAutoRefresh();
      this.startAutoRefresh();
    }
  }

  private startAutoRefresh(): void {
    this.stopAutoRefresh();
    // Initial fetch
    this.refreshAll();

    const scheduleNext = () => {
      if (!this.autoRefreshEnabled()) return;

      // Adaptive cadence: poll every 2s during sync, back off to 8s if offline, or standard interval
      let delayMs = this.refreshIntervalSec() * 1000;
      if (this.isSyncing()) {
        delayMs = 2000;
      } else if (!this.isBackendOnline()) {
        delayMs = 8000;
      }

      this.refreshTimer = setTimeout(() => {
        if (this.autoRefreshEnabled()) {
          this.fetchStatus().subscribe(() => {
            this.fetchLogs().subscribe();
            scheduleNext();
          });
        }
      }, delayMs);
    };

    scheduleNext();
  }

  private stopAutoRefresh(): void {
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      clearInterval(this.refreshTimer);
      this.refreshTimer = null;
    }
  }

  refreshAll(): void {
    this.fetchStatus().subscribe();
    this.fetchDiagnostics().subscribe();
    this.fetchLogs().subscribe();
    this.fetchVouchers().subscribe();
  }

  clearError(): void {
    this.errorMessage.set(null);
  }

  clearActionMessage(): void {
    this.activeActionMessage.set(null);
  }
}
