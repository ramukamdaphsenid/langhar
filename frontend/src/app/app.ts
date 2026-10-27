import { Component, effect, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { TallyApiService } from './services/tally-api.service';
import { BillService } from './services/bill.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.html',
})
export class App {
  readonly tallyService = inject(TallyApiService);
  private readonly billService = inject(BillService);

  constructor() {
    this.tallyService.refreshActiveCompany().subscribe();
    effect(() => {
      const companyId = this.tallyService.activeCompanyId();
      const companyName = this.tallyService.activeCompany();
      if (!companyId || !companyName) return;

      this.billService.activateCompany(companyId, companyName);
      this.tallyService.fetchCompanyProfile(companyId).subscribe(profile => {
        if (profile && companyId === this.tallyService.activeCompanyId()) {
          this.billService.setCompanyProfile(profile, true);
        }
      });
    });
  }

}
