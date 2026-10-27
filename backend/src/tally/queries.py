"""Tally Prime XML / TDL Request Templates.

Tally Prime uses XML over HTTP (port 9000 by default).
Requests are structured using Tally Definition Language (TDL) envelopes.
"""
from typing import Optional, Sequence
from xml.sax.saxutils import escape


VOUCHER_SCREEN_TYPES = ("RICE SALES", "RICE SALES TAXABLE")


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



def build_vouchers_query(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    company: Optional[str] = None,
    voucher_types: Optional[Sequence[str]] = None,
) -> str:
    """Build a TDL query for all voucher types or a selected set of types.

    Args:
        from_date: Start date in YYYYMMDD format (e.g. '20240401'). Defaults to beginning of financial year if omitted.
        to_date: End date in YYYYMMDD format (e.g. '20240430'). Defaults to current date if omitted.
        company: Optional target company name in Tally.
        voucher_types: Optional voucher type names to include in the export.
    """
    # Build Static Variables block
    static_vars = ["<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>"]
    # `company` is retained for call compatibility, but deliberately not sent as
    # SVCURRENTCOMPANY: Tally's XML implementation can crash on context switching.
    if from_date:
        static_vars.append(f"<SVFROMDATE>{from_date}</SVFROMDATE>")
    if to_date:
        static_vars.append(f"<SVTODATE>{to_date}</SVTODATE>")

    static_vars_xml = "\n        ".join(static_vars)

    filters = []
    formulae = []

    if voucher_types:
        escaped_types = [escape(voucher_type, {'"': "&quot;"}) for voucher_type in voucher_types]
        type_checks = " OR ".join(
            f'$$IsEqual:$VoucherTypeName:"{voucher_type}"' for voucher_type in escaped_types
        )
        filters.append("<FILTER>FilterByVoucherType</FILTER>")
        formulae.append(
            f'<SYSTEM TYPE="Formulae" NAME="FilterByVoucherType">{type_checks}</SYSTEM>'
        )

    filters_xml = "\n              ".join(filters)
    formulae_xml = "\n          ".join(formulae)

    # Fetch only data rendered on the voucher screen and its invoice/delivery actions.
    fetch_fields = (
        "GUID,VOUCHERNUMBER,DATE,VOUCHERTYPENAME,"
        "PARTYLEDGERNAME,PARTYNAME,STATENAME,PLACEOFSUPPLY,PARTYGSTIN,"
        "BASICSHIPVESSELNO,VEHICLENO,EWAYBILLDETAILS.LIST.VEHICLENO,"
        "EWAYBILLDETAILS.LIST.BASICSHIPVESSELNO,NARRATION,REFERENCE,"
        "ALLLEDGERENTRIES.LIST.LEDGERNAME,ALLLEDGERENTRIES.LIST.AMOUNT,"
        "ALLLEDGERENTRIES.LIST.INVENTORYALLOCATIONS.LIST.STOCKITEMNAME,"
        "ALLLEDGERENTRIES.LIST.INVENTORYALLOCATIONS.LIST.BILLEDQTY,"
        "ALLLEDGERENTRIES.LIST.INVENTORYALLOCATIONS.LIST.ACTUALQTY,"
        "ALLLEDGERENTRIES.LIST.INVENTORYALLOCATIONS.LIST.RATE,"
        "ALLLEDGERENTRIES.LIST.INVENTORYALLOCATIONS.LIST.AMOUNT,"
        "ALLLEDGERENTRIES.LIST.INVENTORYALLOCATIONS.LIST.BATCHALLOCATIONS.LIST.BATCHNAME,"
        "ALLLEDGERENTRIES.LIST.INVENTORYALLOCATIONS.LIST.BATCHALLOCATIONS.LIST.GODOWNNAME,"
        "ALLINVENTORYENTRIES.LIST.STOCKITEMNAME,ALLINVENTORYENTRIES.LIST.BILLEDQTY,"
        "ALLINVENTORYENTRIES.LIST.ACTUALQTY,ALLINVENTORYENTRIES.LIST.RATE,"
        "ALLINVENTORYENTRIES.LIST.AMOUNT,"
        "ALLINVENTORYENTRIES.LIST.BATCHALLOCATIONS.LIST.BATCHNAME,"
        "ALLINVENTORYENTRIES.LIST.BATCHALLOCATIONS.LIST.GODOWNNAME"
    )

    query = f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>VoucherCollection</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        {static_vars_xml}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="VoucherCollection" ISMODIFY="No">
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


def build_sales_vouchers_query(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    company: Optional[str] = None
) -> str:
    """Backward-compatible alias; query now exports every voucher type."""
    return build_vouchers_query(from_date, to_date, company)
