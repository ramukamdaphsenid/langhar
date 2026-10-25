export interface CompanyProfile {
  company_name: string;
  tagline?: string;
  address: string;
  state?: string;
  gstin: string;
  pan?: string;
  phone?: string;
  email?: string;
  bank_name?: string;
  bank_account_number?: string;
  bank_ifsc?: string;
  bank_branch?: string;
  terms?: string;
}

export const DEFAULT_COMPANY_PROFILE: CompanyProfile = {
  company_name: 'Sri Lakshmi Modern Rice Mill',
  tagline: 'Premium Rice Millers & Wholesalers',
  address: '12, Main Road, Bengaluru 560001',
  state: 'Karnataka (State Code: 29)',
  gstin: '29AABCL1234F1Z5',
  pan: 'AABCL1234F',
  phone: '+91 98765 43210',
  email: 'billing@langhar.com',
  bank_name: 'State Bank of India',
  bank_account_number: '39120491823',
  bank_ifsc: 'SBIN0001234',
  bank_branch: 'Main Branch, Bengaluru',
  terms: '1. Goods once sold will not be taken back. 2. Subject to Bengaluru jurisdiction.',
};
