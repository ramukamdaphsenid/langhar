"""Shared Pydantic schemas for the Langhar Tally to Firebase Sync API."""
from typing import Optional

from pydantic import BaseModel, Field

from src.utils.company_helper import DEFAULT_COMPANY_PROFILE


class SyncRequest(BaseModel):
    from_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD or YYYYMMDD)")
    to_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD or YYYYMMDD)")
    full: bool = Field(False, description="Full sync flag, ignores previous AlterID")


class DaemonStartRequest(BaseModel):
    interval: Optional[int] = Field(None, ge=5, le=86400, description="Interval in seconds")


class CompanyProfileModel(BaseModel):
    company_name: str = Field(DEFAULT_COMPANY_PROFILE["company_name"], description="Company / Business Name")
    tagline: Optional[str] = Field(DEFAULT_COMPANY_PROFILE["tagline"], description="Tagline or subtitle")
    address: str = Field(DEFAULT_COMPANY_PROFILE["address"], description="Physical Address")
    state: Optional[str] = Field(DEFAULT_COMPANY_PROFILE["state"], description="State name and GST state code")
    gstin: str = Field(DEFAULT_COMPANY_PROFILE["gstin"], description="GST Identification Number")
    pan: Optional[str] = Field(DEFAULT_COMPANY_PROFILE["pan"], description="Permanent Account Number (PAN)")
    phone: Optional[str] = Field(DEFAULT_COMPANY_PROFILE["phone"], description="Contact phone / mobile number")
    email: Optional[str] = Field(DEFAULT_COMPANY_PROFILE["email"], description="Billing / Contact email")
    bank_name: Optional[str] = Field(DEFAULT_COMPANY_PROFILE["bank_name"], description="Bank Name")
    bank_account_number: Optional[str] = Field(DEFAULT_COMPANY_PROFILE["bank_account_number"], description="Bank Account Number")
    bank_ifsc: Optional[str] = Field(DEFAULT_COMPANY_PROFILE["bank_ifsc"], description="Bank IFSC Code")
    bank_branch: Optional[str] = Field(DEFAULT_COMPANY_PROFILE["bank_branch"], description="Bank Branch Location")
    terms: Optional[str] = Field(DEFAULT_COMPANY_PROFILE["terms"], description="Terms and conditions or invoice footer notes")
