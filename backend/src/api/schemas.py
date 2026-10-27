"""Pydantic schemas for company document information."""
from typing import Optional

from pydantic import BaseModel, Field

from src.utils.company_helper import DEFAULT_COMPANY_PROFILE


class CompanyProfileModel(BaseModel):
    company_name: str = Field(DEFAULT_COMPANY_PROFILE["company_name"], description="Company / Business Name")
    tagline: Optional[str] = Field(DEFAULT_COMPANY_PROFILE["tagline"], description="Tagline or subtitle")
    address: str = Field(DEFAULT_COMPANY_PROFILE["address"], description="Physical Address")
    state: Optional[str] = Field(DEFAULT_COMPANY_PROFILE["state"], description="State name and GST state code")
    gstin: str = Field(DEFAULT_COMPANY_PROFILE["gstin"], description="GST Identification Number")
    pan: Optional[str] = Field(DEFAULT_COMPANY_PROFILE["pan"], description="Permanent Account Number (PAN)")
    phone: Optional[str] = Field(DEFAULT_COMPANY_PROFILE["phone"], description="Contact phone / mobile number")
    email: Optional[str] = Field(DEFAULT_COMPANY_PROFILE["email"], description="Billing / Contact email")
