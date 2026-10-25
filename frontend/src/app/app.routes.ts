import { Routes } from '@angular/router';
import { VouchersExplorer } from './components/vouchers-explorer/vouchers-explorer';
import { SettingsView } from './components/settings-view/settings-view';

export const appRoutes: Routes = [
  { path: '', redirectTo: '/vouchers', pathMatch: 'full' },
  { path: 'vouchers', component: VouchersExplorer },
  { path: 'settings', component: SettingsView },
  { path: '**', redirectTo: '/vouchers' },
];
