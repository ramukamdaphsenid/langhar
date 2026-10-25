import { Injectable } from '@angular/core';
import type { SaleRecord } from '../models/bill.model';
import { environment } from '../../environments/environment';
import { lexendVfs, lexendFontMap } from './lexend-fonts';
import { CompanyProfile, DEFAULT_COMPANY_PROFILE } from '../models/company.model';
import { buildDeliveryNoteDoc, buildInvoiceDoc } from './bill-pdf.builder';
import type { TDocumentDefinitions } from 'pdfmake/interfaces';

export type BillConfig = CompanyProfile;

@Injectable({ providedIn: 'root' })
export class BillService {
  private readonly storageKey = 'langhar_company_profile';
  private config: CompanyProfile = this.loadInitialConfig();
  private pdfMakePromise: Promise<any> | null = null;
  private logoBase64: string | null = null;

  private loadInitialConfig(): CompanyProfile {
    if (typeof localStorage !== 'undefined') {
      try {
        const saved = localStorage.getItem(this.storageKey);
        if (saved) {
          const parsed = JSON.parse(saved);
          return { ...DEFAULT_COMPANY_PROFILE, ...parsed };
        }
      } catch {}
    }
    return {
      ...DEFAULT_COMPANY_PROFILE,
      company_name: environment.companyName || DEFAULT_COMPANY_PROFILE.company_name,
      address: environment.address || DEFAULT_COMPANY_PROFILE.address,
      gstin: environment.gstin || DEFAULT_COMPANY_PROFILE.gstin,
    };
  }

  getConfig(): CompanyProfile {
    return { ...this.config };
  }

  setCompanyProfile(profile: Partial<CompanyProfile>, overwrite = false): void {
    if (overwrite) {
      this.config = { ...DEFAULT_COMPANY_PROFILE, ...profile };
    } else {
      this.config = { ...this.config, ...profile };
    }
    if (typeof localStorage !== 'undefined') {
      try {
        localStorage.setItem(this.storageKey, JSON.stringify(this.config));
      } catch {}
    }
  }

  getSampleSaleRecord(): SaleRecord {
    return {
      voucherNumber: 'INV-2026-0042',
      dateISO: new Date().toISOString().slice(0, 10),
      partyName: 'Sri Raghavendra Traders',
      partyAddress: 'Shop #14, APMC Market Yard, Yeshwanthpur, Bengaluru 560022',
      partyState: 'Karnataka (29)',
      partyGstin: '29ABCDE1234F1Z5',
      deliveryNote: 'DEL-8841',
      items: [
        {
          name: 'Langhar Sona Masoori Raw Rice (26kg Bag)',
          quantity: 100,
          unit: 'BAG',
          rate: 1450,
          amount: 145000,
        },
        {
          name: 'Langhar Steam Rice Royal (50kg Bag)',
          quantity: 40,
          unit: 'BAG',
          rate: 2650,
          amount: 106000,
        },
      ],
      totalAmount: 263550,
      totalGst: 12550,
      narration: 'Payment due in 15 days via RTGS/NEFT to our specified bank account.',
      rowId: 'sample-voucher-preview',
    };
  }

  private loadPdfMake(): Promise<any> {
    if (!this.pdfMakePromise) {
      this.pdfMakePromise = (async () => {
        const pdfModule = await import('pdfmake/build/pdfmake');
        const pdfMake = pdfModule.default ?? pdfModule;
        const vfsModule = await import('pdfmake/build/vfs_fonts');
        const vfs = vfsModule.default ?? vfsModule;
        pdfMake.addVirtualFileSystem(vfs);
        pdfMake.addVirtualFileSystem(lexendVfs);
        pdfMake.addFonts(lexendFontMap);
        return pdfMake;
      })();
    }
    return this.pdfMakePromise;
  }

  private async loadLogo(): Promise<string> {
    if (this.logoBase64) {
      return this.logoBase64;
    }
    try {
      const response = await fetch('logo.png');
      if (!response.ok) throw new Error('Failed to fetch logo');
      const blob = await response.blob();
      this.logoBase64 = await new Promise<string>((resolve) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result as string);
        reader.readAsDataURL(blob);
      });
      return this.logoBase64;
    } catch {
      return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';
    }
  }

  private async generatePdf(sale: SaleRecord, builder: (logoDataUri: string) => TDocumentDefinitions): Promise<Blob> {
    const [pdfModule, logoDataUri] = await Promise.all([
      this.loadPdfMake(),
      this.loadLogo(),
    ]);
    const pdfDoc = pdfModule.createPdf(builder(logoDataUri));
    let blob: Blob;
    const blobResult = pdfDoc.getBlob();
    if (blobResult && typeof (blobResult as any).then === 'function') {
      blob = await blobResult;
    } else {
      blob = await new Promise<Blob>((resolve) => (pdfDoc as any).getBlob(resolve));
    }
    return blob;
  }

  async openPdf(sale: SaleRecord): Promise<void> {
    const blob = await this.generatePdf(sale, (logoDataUri) => buildInvoiceDoc(sale, this.config, logoDataUri));
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank');
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }

  async downloadPdf(sale: SaleRecord): Promise<void> {
    const blob = await this.generatePdf(sale, (logoDataUri) => buildInvoiceDoc(sale, this.config, logoDataUri));
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `invoice-${sale.voucherNumber || 'invoice'}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }

  async openDeliveryNotePdf(sale: SaleRecord): Promise<void> {
    const blob = await this.generatePdf(sale, (logoDataUri) => buildDeliveryNoteDoc(sale, this.config, logoDataUri));
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank');
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }

  async downloadDeliveryNotePdf(sale: SaleRecord): Promise<void> {
    const blob = await this.generatePdf(sale, (logoDataUri) => buildDeliveryNoteDoc(sale, this.config, logoDataUri));
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `delivery-note-${sale.voucherNumber || 'challan'}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }
}
