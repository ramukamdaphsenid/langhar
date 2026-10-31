import { Routes } from '@angular/router';

export const appRoutes: Routes = [
  { path: '', redirectTo: '/vouchers', pathMatch: 'full' },
  { path: 'vouchers', loadComponent: () => import('./components/vouchers-explorer/vouchers-explorer').then(m => m.VouchersExplorer) },
  { path: '**', redirectTo: '/vouchers' },
];
