"""Tally Prime XML / TDL Request Templates.

Tally Prime uses XML over HTTP (port 9000 by default).
Requests are structured using Tally Definition Language (TDL) envelopes.
"""
from typing import Optional


def build_company_info_query() -> str:
    """Safe built-in Tally XML request to retrieve loaded companies.

    Uses Tally's native Company collection export request.
    This does NOT use any custom ad-hoc TDL scripts or unallocated '##' macros,
    which prevents Memory Access Violations (c0000005) in Tally Prime.
    """
    return """<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>Company</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
    </DESC>
  </BODY>
</ENVELOPE>"""



def build_active_company_query() -> str:
    """Safe native List of Companies request."""
    return build_company_info_query()


def build_sales_vouchers_query(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    from_alter_id: Optional[int] = None,
    company: Optional[str] = None
) -> str:
    """Builds a TDL Collection XML query to extract sales vouchers with full nested details.

    Args:
        from_date: Start date in YYYYMMDD format (e.g. '20240401'). Defaults to beginning of financial year if omitted.
        to_date: End date in YYYYMMDD format (e.g. '20240430'). Defaults to current date if omitted.
        from_alter_id: If provided, fetches vouchers where $ALTERID > from_alter_id (for incremental sync).
        company: Optional target company name in Tally.
    """
    # Build Static Variables block
    static_vars = ["<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>"]
    if company and company.strip():
        clean_company = (
            company.strip()
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        static_vars.append(f"<SVCURRENTCOMPANY>{clean_company}</SVCURRENTCOMPANY>")
    if from_date:
        static_vars.append(f"<SVFROMDATE>{from_date}</SVFROMDATE>")
    if to_date:
        static_vars.append(f"<SVTODATE>{to_date}</SVTODATE>")

    static_vars_xml = "\n        ".join(static_vars)

    # Build Filter formulas: Filter strictly for RICE SALES and RICE SALES TAXABLE
    filters = ["<FILTER>IsRiceSalesVoucher</FILTER>"]
    formulae = [
        """<SYSTEM TYPE="Formulae" NAME="IsRiceSalesVoucher">
            ($VoucherTypeName = "RICE SALES") OR ($VoucherTypeName = "RICE SALES TAXABLE")
          </SYSTEM>"""
    ]

    if from_alter_id is not None and from_alter_id > 0:
        filters.append("<FILTER>FilterByAlterId</FILTER>")
        formulae.append(
            f"""<SYSTEM TYPE="Formulae" NAME="FilterByAlterId">
            $AlterID &gt; {from_alter_id}
          </SYSTEM>"""
        )

    filters_xml = "\n              ".join(filters)
    formulae_xml = "\n          ".join(formulae)

    # Request full voucher fields
    fetch_fields = (
        "GUID,ALTERID,MASTERID,VOUCHERNUMBER,DATE,EFFECTIVEDATE,VOUCHERTYPENAME,"
        "PARTYLEDGERNAME,PARTYNAME,STATENAME,PLACEOFSUPPLY,PARTYGSTIN,GSTREGISTRATIONTYPE,"
        "BASICSHIPVESSELNO,VEHICLENO,BASICSHIPPEDBY,EWAYBILLDETAILS.LIST,"
        "NARRATION,REFERENCE,ALLLEDGERENTRIES.LIST,ALLINVENTORYENTRIES.LIST"
    )

    query = f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>SalesVoucherCollection</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        {static_vars_xml}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="SalesVoucherCollection" ISMODIFY="No">
            <TYPE>Voucher</TYPE>
            <FETCH>{fetch_fields}</FETCH>
            {filters_xml}
          </COLLECTION>
          {formulae_xml}
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>"""
    return query
