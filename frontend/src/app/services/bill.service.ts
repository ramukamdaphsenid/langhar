import { Injectable } from '@angular/core';
import type { SaleRecord } from '../models/bill.model';
import { lexendFontMap, loadLexendFontVfs } from './lexend-fonts';
import { CompanyProfile } from '../models/company.model';
import { buildDeliveryNoteDoc, buildInvoiceDoc } from './bill-pdf.builder';
import type { TDocumentDefinitions } from 'pdfmake/interfaces';

@Injectable({ providedIn: 'root' })
export class BillService {
  private config: CompanyProfile = this.loadInitialConfig();
  private pdfMakePromise: Promise<any> | null = null;
  private logoPromise: Promise<string> | null = null;

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

  activateCompany(companyName: string): void {
    this.config = { ...this.loadInitialConfig(), company_name: companyName.trim() };
  }

  setCompanyProfile(profile: Partial<CompanyProfile>, overwrite = false): void {
    this.config = overwrite
      ? { ...this.loadInitialConfig(), ...profile }
      : { ...this.config, ...profile };
  }

  private initializationPromise: Promise<{ pdfMake: any; logoDataUri: string }> | null = null;

  private async initializePdfAssets(): Promise<{ pdfMake: any; logoDataUri: string }> {
    if (!this.initializationPromise) {
      this.initializationPromise = (async () => {
        // Load PDF maker with fonts
        const pdfModule = await import('pdfmake/build/pdfmake');
        const pdfMake = pdfModule.default ?? pdfModule;
        pdfMake.addVirtualFileSystem(await loadLexendFontVfs());
        pdfMake.addFonts(lexendFontMap);

        // Load logo with fallback
        let logoDataUri: string;
        try {
          const response = await fetch('/pdf-logo.png');
          if (!response.ok) throw new Error('Failed to fetch PDF logo');
          const blob = await response.blob();
          logoDataUri = await new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result as string);
            reader.onerror = () => reject(new Error('Failed to read PDF logo'));
            reader.readAsDataURL(blob);
          });
        } catch {
          logoDataUri = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';
        }

        return { pdfMake, logoDataUri };
      })();
    }
    return this.initializationPromise;
  }

  private async loadPdfMake(): Promise<any> {
    return (await this.initializePdfAssets()).pdfMake;
  }

  private async loadLogo(): Promise<string> {
    return (await this.initializePdfAssets()).logoDataUri;
  }

  private async generatePdf(builder: (logoDataUri: string) => TDocumentDefinitions): Promise<Blob> {
    const assets = await this.initializePdfAssets();
    const pdfDoc = assets.pdfMake.createPdf(builder(assets.logoDataUri));
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
