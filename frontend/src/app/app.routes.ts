import { Routes } from '@angular/router';

export const appRoutes: Routes = [
  { path: '', redirectTo: '/vouchers', pathMatch: 'full' },
  { path: 'vouchers', loadComponent: () => import('./components/vouchers-explorer/vouchers-explorer').then(m => m.VouchersExplorer) },
  { path: 'company', redirectTo: '/vouchers' },
  { path: 'settings', redirectTo: '/vouchers' },
  { path: 'workspace', redirectTo: '/vouchers' },
  { path: '**', redirectTo: '/vouchers' },
];
