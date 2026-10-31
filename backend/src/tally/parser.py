"""Parser for Tally XML voucher responses.

Transforms raw Tally XML responses into clean, normalized Python dictionaries
ready for validation and use by the frontend.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
import xmltodict

from src.utils.logger import logger


def ensure_list(item: Any) -> List[Any]:
    """Ensures that the input is converted to a list if it's a single item or dict."""
    if item is None:
        return []
    if isinstance(item, list):
        return item
    return [item]


def safe_str(val: Any) -> str:
    """Safely extracts string representation, stripping extra whitespace and unwrapping XML dicts."""
    if val is None:
        return ""
    if isinstance(val, dict):
        return str(val.get("#text", "")).strip()
    return str(val).strip()


def parse_tally_quantity(raw_qty: Any) -> Tuple[float, str]:
    """Extracts numeric quantity and unit from Tally quantity string.

    If dual/alternate units are present (e.g. '25.00 QTL = 100 BAG'),
    it prioritizes the BAG count over weight units like QTL.
    """
    s = safe_str(raw_qty).replace(",", "").strip()
    s = re.sub(r"^=+\s*", "", s)
    if not s:
        return 0.0, ""

    segments = [seg.strip() for seg in s.split("=") if re.search(r"\d", seg)]
    if not segments:
        return 0.0, ""

    parsed_segments = []
    for seg in segments:
        m = re.search(r"[-+]?\d*\.?\d+", seg)
        if m:
            val = abs(float(m.group(0)))
            rest = seg.replace(m.group(0), "").strip()
            u_match = re.search(r"[a-zA-Z]+", rest)
            u = u_match.group(0).strip() if u_match else ""
            parsed_segments.append((val, u))

    if not parsed_segments:
        return 0.0, ""

    # 1. Prioritize BAG units
    for val, u in parsed_segments:
        if re.match(r"^(bag|bags|bgs|bg)$", u, re.IGNORECASE):
            return val, u

    # 2. Prioritize non-weight packaging units over bulk weight (QTL, KGS)
    weight_pattern = re.compile(r"^(qtl|qntl|quintal|quintals|kg|kgs|mt|ton|tons|tonne|tonnes)$", re.IGNORECASE)
    has_weight = any(weight_pattern.match(u) for _, u in parsed_segments if u)
    if has_weight:
        for val, u in parsed_segments:
            if u and not weight_pattern.match(u):
                return val, u

    # 3. Default to first segment
    return parsed_segments[0]


def safe_float(val: Any, default: float = 0.0) -> float:
    """Safely parses float numbers from Tally strings/dicts (handling negatives, units, commas)."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, dict):
        val = val.get("#text", "")

    s = safe_str(val)
    if not s:
        return default

    if "=" in s:
        qty, _ = parse_tally_quantity(s)
        return qty

    cleaned = re.sub(r"[^\d.-]", "", s.split("/")[0])
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return default


def safe_int(val: Any, default: int = 0) -> int:
    """Safely parses integer values from strings or XML dicts."""
    if val is None:
        return default
    if isinstance(val, dict):
        val = val.get("#text", "")
    try:
        return int(safe_float(val, default))
    except (ValueError, TypeError):
        return default


def parse_tally_date(date_str: str) -> Optional[str]:
    """Converts Tally YYYYMMDD date format into ISO YYYY-MM-DD.

    Example: '20240401' -> '2024-04-01'
    """
    s = safe_str(date_str)
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    # Fallback if already formatted
    return s if s else None


def parse_inventory_entries(raw_entries: Any) -> List[Dict[str, Any]]:
    """Normalizes inventory line items (products, quantities, rates, amounts)."""
    items = []
    for entry in ensure_list(raw_entries):
        if not isinstance(entry, dict):
            continue

        item_name = safe_str(entry.get("STOCKITEMNAME"))
        if not item_name:
            continue

        billed_qty_str = safe_str(entry.get("BILLEDQTY"))
        actual_qty_str = safe_str(entry.get("ACTUALQTY"))
        
        # Parse numeric quantity & unit (prioritizing BAG count over QTL in dual units)
        qty_num, unit = parse_tally_quantity(billed_qty_str or actual_qty_str)

        rate_str = safe_str(entry.get("RATE"))
        rate_num = safe_float(rate_str)

        if not unit:
            if "/" in rate_str:
                unit = rate_str.split("/")[-1].strip()
            elif billed_qty_str:
                unit_match = re.search(r"[a-zA-Z]+", billed_qty_str)
                if unit_match:
                    unit = unit_match.group(0).strip()

        # Amount in Tally credit is often negative, convert to absolute for item line amount
        amount = abs(safe_float(entry.get("AMOUNT")))
        discount = safe_float(entry.get("DISCOUNT"))

        # Batch allocations if applicable
        batch_list = []
        raw_batches = entry.get("BATCHALLOCATIONS.LIST")
        for b in ensure_list(raw_batches):
            if isinstance(b, dict):
                b_billed = safe_str(b.get("BILLEDQTY"))
                b_qty, b_unit = parse_tally_quantity(b_billed)
                batch_list.append({
                    "batch_name": safe_str(b.get("BATCHNAME")),
                    "godown_name": safe_str(b.get("GODOWNNAME")),
                    "amount": abs(safe_float(b.get("AMOUNT"))),
                    "billed_qty": b_billed,
                    "quantity": b_qty,
                    "unit": b_unit,
                })

        items.append({
            "item_name": item_name,
            "billed_qty": billed_qty_str or (f"{qty_num} {unit}".strip() if qty_num else ""),
            "quantity": qty_num,
            "rate": rate_num,
            "rate_raw": rate_str,
            "unit": unit,
            "amount": amount,
            "discount": discount,
            "batches": batch_list,
        })
    return items


def parse_ledger_entries(raw_entries: Any) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    """Normalizes ledger line items and aggregates tax amounts (CGST, SGST, IGST)."""
    ledgers = []
    taxes = {
        "cgst": 0.0,
        "sgst": 0.0,
        "igst": 0.0,
        "round_off": 0.0,
        "other_charges": 0.0
    }

    for entry in ensure_list(raw_entries):
        if not isinstance(entry, dict):
            continue

        ledger_name = safe_str(entry.get("LEDGERNAME"))
        if not ledger_name:
            continue

        raw_amount = safe_float(entry.get("AMOUNT"))
        is_positive = safe_str(entry.get("ISDEEMEDPOSITIVE")).lower() in ("yes", "true", "1")

        # In Tally, ledger amounts are negative for credit and positive for debit.
        abs_amount = abs(raw_amount)

        name_lower = ledger_name.lower()
        if "cgst" in name_lower:
            taxes["cgst"] += abs_amount
        elif "sgst" in name_lower or "utgst" in name_lower:
            taxes["sgst"] += abs_amount
        elif "igst" in name_lower:
            taxes["igst"] += abs_amount
        elif "round" in name_lower and "off" in name_lower:
            taxes["round_off"] += raw_amount  # Can be positive or negative
        elif any(charge in name_lower for charge in ["freight", "shipping", "delivery", "packing", "tcs"]):
            taxes["other_charges"] += abs_amount

        ledgers.append({
            "ledger_name": ledger_name,
            "amount": abs_amount,
            "raw_amount": raw_amount,
            "is_deemed_positive": is_positive,
        })

    return ledgers, taxes


def extract_vehicle_number(v_data: Dict[str, Any], narration: str = "", reference: str = "") -> str:
    """Extracts vehicle/transport number from Tally voucher fields or narration.

    Checks:
    1. BASICSHIPVESSELNO (Tally standard dispatch/vessel/vehicle field)
    2. VEHICLENO (Tally standard e-way bill / transport / custom UDF tag)
    3. EWAYBILLDETAILS.LIST -> VEHICLENO / BASICSHIPVESSELNO
    4. SHIPPINGDETAILS.LIST / DISPATCHDETAILS.LIST
    5. Regex extraction from reference or narration
    """
    # 1. Native / UDF tags on voucher level
    v_no = safe_str(v_data.get("BASICSHIPVESSELNO")) or safe_str(v_data.get("VEHICLENO"))
    if v_no:
        return v_no

    # 2. Check EWAYBILLDETAILS.LIST
    eway_list = ensure_list(v_data.get("EWAYBILLDETAILS.LIST"))
    for entry in eway_list:
        if isinstance(entry, dict):
            cand = safe_str(entry.get("VEHICLENO")) or safe_str(entry.get("BASICSHIPVESSELNO")) or safe_str(entry.get("VEHICLE_NO"))
            if cand:
                return cand

    # 3. Check DISPATCHDETAILS / SHIPPINGDETAILS
    for list_key in ("DISPATCHDETAILS.LIST", "SHIPPINGDETAILS.LIST"):
        for entry in ensure_list(v_data.get(list_key)):
            if isinstance(entry, dict):
                cand = safe_str(entry.get("BASICSHIPVESSELNO")) or safe_str(entry.get("VEHICLENO"))
                if cand:
                    return cand

    # 4. Check fallback regex in reference and narration
    text_corpus = f"{reference} {narration}"
    explicit_match = re.search(
        r"(?i)(?:veh(?:icle)?(?:\s*no\.?|\s*number)?|truck(?:\s*no\.?|\s*number)?|lorry(?:\s*no\.?|\s*number)?|tempo(?:\s*no\.?|\s*number)?)\s*[:\-]?\s*([A-Z0-9 -]{6,16})",
        text_corpus
    )
    if explicit_match:
        cand = explicit_match.group(1).strip()
        cleaned = re.sub(r"[^A-Za-z0-9]", "", cand)
        if len(cleaned) >= 5:
            return cand

    # 5. Standard Indian vehicle registration plate pattern: e.g. MH12DE1432, DL 01 A 1234, KA-04-E-4590
    plate_match = re.search(
        r"\b([A-Z]{2}[ -]?[0-9]{1,2}[ -]?[A-Z]{1,3}[ -]?[0-9]{4})\b",
        text_corpus
    )
    if plate_match:
        return plate_match.group(1).strip()

    return ""


def parse_single_voucher(v_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parses a single Tally voucher dictionary into a standardized schema."""
    if not isinstance(v_data, dict):
        return None

    raw_v_type = (
        safe_str(v_data.get("VOUCHERTYPENAME"))
        or safe_str(v_data.get("@VCHTYPE"))
        or safe_str(v_data.get("VCHTYPE"))
    )
    if not raw_v_type:
        return None

    voucher_type = raw_v_type.strip()

    guid = safe_str(v_data.get("GUID"))
    voucher_number = safe_str(v_data.get("VOUCHERNUMBER"))
    date_iso = parse_tally_date(v_data.get("DATE"))
    master_id = safe_int(v_data.get("MASTERID"))

    # Party details
    party_ledger = safe_str(v_data.get("PARTYLEDGERNAME"))
    party_name = safe_str(v_data.get("PARTYNAME")) or party_ledger
    party_state = safe_str(v_data.get("STATENAME"))
    place_of_supply = safe_str(v_data.get("PLACEOFSUPPLY")) or party_state
    party_gstin = safe_str(v_data.get("PARTYGSTIN"))
    gst_reg_type = safe_str(v_data.get("GSTREGISTRATIONTYPE"))

    narration = safe_str(v_data.get("NARRATION"))
    reference = safe_str(v_data.get("REFERENCE"))

    vehicle_number = extract_vehicle_number(v_data, narration=narration, reference=reference)

    # Parse items & ledgers
    items = parse_inventory_entries(v_data.get("ALLINVENTORYENTRIES.LIST"))
    # If no items in top-level ALLINVENTORYENTRIES, check nested within ALLLEDGERENTRIES.LIST
    if not items:
        nested_items = []
        for l in ensure_list(v_data.get("ALLLEDGERENTRIES.LIST")):
            if isinstance(l, dict) and "INVENTORYALLOCATIONS.LIST" in l:
                nested_items.extend(parse_inventory_entries(l.get("INVENTORYALLOCATIONS.LIST")))
        items = nested_items

    ledgers, taxes = parse_ledger_entries(v_data.get("ALLLEDGERENTRIES.LIST"))

    # Calculate Total Amount
    # Usually the party ledger entry represents the total invoice amount in a sales voucher
    total_amount = 0.0
    for l in ledgers:
        if l["ledger_name"].lower() == party_ledger.lower():
            total_amount = l["amount"]
            break

    # If party ledger not explicitly matched in entries, sum items + taxes
    if total_amount == 0.0:
        items_total = sum(i["amount"] for i in items)
        tax_total = taxes["cgst"] + taxes["sgst"] + taxes["igst"] + taxes["other_charges"] + taxes["round_off"]
        total_amount = round(items_total + tax_total, 2)
        if total_amount == 0.0 and ledgers:
            # Fallback to max ledger amount
            total_amount = max(l["amount"] for l in ledgers)

    # Stable document ID: clean GUID or sanitized fallback
    if guid:
        doc_id = f"tally_{guid.replace('-', '_')}"
    elif master_id > 0:
        doc_id = f"tally_master_{master_id}"
    else:
        raw_id = f"vch_{voucher_type}_{voucher_number}_{date_iso or 'nodate'}"
        # Sanitize against special characters (#, ?, /, \, *, etc.) invalid for document paths
        clean_suffix = re.sub(r"[^a-zA-Z0-9_\-]", "_", raw_id)
        doc_id = clean_suffix

    return {
        "doc_id": doc_id,
        "guid": guid,
        "voucher_number": voucher_number,
        "voucher_type": voucher_type,
        "date": date_iso,
        "vehicle_number": vehicle_number,
        "party": {
            "ledger_name": party_ledger,
            "name": party_name,
            "state": party_state,
            "place_of_supply": place_of_supply,
            "gstin": party_gstin,
            "gst_registration_type": gst_reg_type,
        },
        "total_amount": round(total_amount, 2),
        "narration": narration,
        "reference": reference,
        "inventory_entries": items,
        "ledger_entries": ledgers,
        "taxes": taxes,
    }


def parse_tally_vouchers_xml(xml_content: str) -> List[Dict[str, Any]]:
    """Parses a full Tally XML response into a list of normalized voucher dicts."""
    if not xml_content or not xml_content.strip():
        return []

    # Sanitize invalid XML 1.0 control character entities emitted by Tally (e.g. &#4;)
    clean_xml = re.sub(r"&#(?:0?[0-8]|1[12]|1[4-9]|2[0-9]|3[01]);", "", xml_content)

    try:
        parsed_dict = xmltodict.parse(
            clean_xml,
            dict_constructor=dict,
            process_namespaces=False,
            strip_whitespace=True
        )
    except Exception as e:
        logger.error(f"Failed to parse Tally XML response: {e}")
        return []

    # Navigate Tally envelope structure
    envelope = parsed_dict.get("ENVELOPE", {})
    body = envelope.get("BODY", {})
    data = body.get("DATA", {})

    # Tally can wrap vouchers in COLLECTION or VOUCHER directly
    collection = data.get("COLLECTION", {})
    raw_vouchers = collection.get("VOUCHER", [])
    if not raw_vouchers and "TALLYMESSAGE" in data:
        # Standard Export Data format
        messages = ensure_list(data["TALLYMESSAGE"])
        raw_vouchers = [m.get("VOUCHER") for m in messages if isinstance(m, dict) and "VOUCHER" in m]

    voucher_list = ensure_list(raw_vouchers)
    results = []

    for v in voucher_list:
        if not v or not isinstance(v, dict):
            continue
        parsed = parse_single_voucher(v)
        if parsed:
            results.append(parsed)

    return results
