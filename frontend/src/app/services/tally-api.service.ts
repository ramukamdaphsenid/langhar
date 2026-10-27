import { Injectable, inject, signal } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, catchError, finalize, map, of, tap } from 'rxjs';
import { ActiveCompanyResponse, VoucherItem, VouchersResponse } from '../models/tally-voucher.model';
import { CompanyProfile } from '../models/company.model';
import { ALLOWED_VOUCHER_TYPES } from './bill.mapper';

@Injectable({ providedIn: 'root' })
export class TallyApiService {
  private readonly http = inject(HttpClient);
  private readonly storageKey = 'tally_sync_api_base_url';
  private voucherRequestVersion = 0;

  readonly apiBaseUrl = signal<string>(this.getInitialBaseUrl());
  readonly vouchers = signal<VoucherItem[]>([]);
  readonly lastVouchersUpdatedAt = signal<Date | null>(null);
  readonly activeCompany = signal<string | null>(null);
  readonly activeCompanyId = signal<string | null>(null);
  readonly isLoadingVouchers = signal(false);
  readonly isBackendOnline = signal(false);
  readonly isCheckingHealth = signal(false);
  readonly activeActionMessage = signal<string | null>(null);
  readonly errorMessage = signal<string | null>(null);

  private getInitialBaseUrl(): string {
    const saved = localStorage.getItem(this.storageKey);
    if (saved) return saved;
    return typeof window !== 'undefined' ? '' : 'http://localhost:8000';
  }

  private getUrl(endpoint: string): string {
    const base = this.apiBaseUrl();
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    return `${base}${cleanEndpoint}`;
  }

  setActiveCompany(companyName: string | null, companyId: string | null = null): void {
    const name = companyName?.trim() || null;
    const id = name ? companyId : null;
    if (name === this.activeCompany() && id === this.activeCompanyId()) return;

    this.activeCompany.set(name);
    this.activeCompanyId.set(id);
    this.vouchers.set([]);
    this.lastVouchersUpdatedAt.set(null);
    this.isLoadingVouchers.set(false);
    this.voucherRequestVersion++;
    if (id) this.fetchVouchers(id).subscribe();
  }

  refreshActiveCompany(): Observable<ActiveCompanyResponse | null> {
    this.isCheckingHealth.set(true);
    const previousCompanyId = this.activeCompanyId();
    return this.http.get<ActiveCompanyResponse>(this.getUrl('/api/company/active')).pipe(
      tap(response => {
        this.isCheckingHealth.set(false);
        const active = response.active_company;
        this.isBackendOnline.set(response.tally_online && !!active);
        this.setActiveCompany(active?.company_name || null, active?.company_id || null);
        if (active && previousCompanyId === active.company_id) {
          this.fetchVouchers(active.company_id).subscribe();
        }
        if (response.tally_online && active) {
          this.errorMessage.set(null);
        } else {
          this.errorMessage.set('Tally is not reachable or its active company could not be verified.');
        }
      }),
      catchError((error: HttpErrorResponse) => {
        this.isCheckingHealth.set(false);
        this.isBackendOnline.set(false);
        this.setActiveCompany(null);
        this.errorMessage.set(error.error?.detail || error.message || 'Could not connect to the Langhar API.');
        return of(null);
      })
    );
  }

  fetchVouchers(companyId = this.activeCompanyId()): Observable<VoucherItem[] | null> {
    const requestVersion = ++this.voucherRequestVersion;
    if (!companyId) {
      this.vouchers.set([]);
      return of(null);
    }

    this.isLoadingVouchers.set(true);
    const query = `?company_id=${encodeURIComponent(companyId)}`;
    return this.http.get<VouchersResponse>(this.getUrl(`/api/vouchers${query}`)).pipe(
      map(response => ({
        ...response,
        vouchers: (response.vouchers || []).filter(voucher =>
          ALLOWED_VOUCHER_TYPES.has((voucher.voucher_type || '').trim().toUpperCase())
        ),
      })),
      tap(response => {
        if (companyId !== this.activeCompanyId() || requestVersion !== this.voucherRequestVersion) return;
        this.vouchers.set(response.vouchers);
        this.lastVouchersUpdatedAt.set(new Date());
        this.isBackendOnline.set(true);
        this.errorMessage.set(null);
      }),
      map(response => response.vouchers),
      catchError((error: HttpErrorResponse) => {
        if (companyId === this.activeCompanyId() && requestVersion === this.voucherRequestVersion) {
          this.vouchers.set([]);
          this.isBackendOnline.set(false);
          this.errorMessage.set(error.error?.detail || error.message || 'Could not load vouchers from Tally Prime.');
        }
        return of(null);
      }),
      finalize(() => {
        if (requestVersion === this.voucherRequestVersion) this.isLoadingVouchers.set(false);
      })
    );
  }

  fetchCompanyProfile(companyId = this.activeCompanyId()): Observable<CompanyProfile | null> {
    if (!companyId) return of(null);
    return this.http.get<CompanyProfile>(
      this.getUrl(`/api/settings/company?company_id=${encodeURIComponent(companyId)}`)
    ).pipe(
      catchError((error: HttpErrorResponse) => {
        this.errorMessage.set(error.error?.detail || error.message || 'Could not load invoice details.');
        return of(null);
      })
    );
  }

  clearError(): void {
    this.errorMessage.set(null);
  }

  clearActionMessage(): void {
    this.activeActionMessage.set(null);
  }
}
