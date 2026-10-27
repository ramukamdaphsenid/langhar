import { Injectable } from '@angular/core';
import type { SaleRecord } from '../models/bill.model';
import { lexendVfs, lexendFontMap } from './lexend-fonts';
import { CompanyProfile } from '../models/company.model';
import { buildDeliveryNoteDoc, buildInvoiceDoc } from './bill-pdf.builder';
import type { TDocumentDefinitions } from 'pdfmake/interfaces';

@Injectable({ providedIn: 'root' })
export class BillService {
  private config: CompanyProfile = this.loadInitialConfig();
  private pdfMakePromise: Promise<any> | null = null;
  private logoBase64: string | null = null;

  private loadInitialConfig(): CompanyProfile {
    return {
      company_name: '',
      tagline: '',
      address: '',
      state: '',
      gstin: '',
      pan: '',
      phone: '',
      email: '',
    };
  }

  getConfig(): CompanyProfile {
    return { ...this.config };
  }

  activateCompany(_companyId: string, companyName: string): void {
    this.config = { ...this.loadInitialConfig(), company_name: companyName.trim() };
  }

  setCompanyProfile(profile: Partial<CompanyProfile>, overwrite = false): void {
    this.config = overwrite
      ? { ...this.loadInitialConfig(), ...profile }
      : { ...this.config, ...profile };
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

  private async generatePdf(builder: (logoDataUri: string) => TDocumentDefinitions): Promise<Blob> {
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

  async generateInvoicePdf(sale: SaleRecord): Promise<Blob> {
    return this.generatePdf((logoDataUri) => buildInvoiceDoc(sale, this.config, logoDataUri));
  }

  async downloadPdf(sale: SaleRecord): Promise<void> {
    const blob = await this.generateInvoicePdf(sale);
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `invoice-${sale.voucherNumber || 'invoice'}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }

  async generateDeliveryNotePdf(sale: SaleRecord): Promise<Blob> {
    return this.generatePdf((logoDataUri) => buildDeliveryNoteDoc(sale, this.config, logoDataUri));
  }

  async downloadDeliveryNotePdf(sale: SaleRecord): Promise<void> {
    const blob = await this.generateDeliveryNotePdf(sale);
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
