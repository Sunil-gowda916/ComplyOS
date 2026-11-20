"""Deterministic validation rules for ComplyMate AI (MVP).

The LLM never decides whether a check passes. Every function here is plain,
testable Python. Each failed check returns an Issue that becomes a tracked
exception in the database.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from rapidfuzz import fuzz

GSTIN_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
ROUNDING_TOLERANCE = Decimal("1.00")


@dataclass
class Invoice:
    supplier_gstin: Optional[str]
    invoice_no: Optional[str]
    invoice_date: Optional[date]
    place_of_supply: Optional[str]  # 2-digit state code
    taxable_value: Optional[Decimal]
    cgst: Decimal = Decimal("0")
    sgst: Decimal = Decimal("0")
    igst: Decimal = Decimal("0")
    total: Optional[Decimal] = None
    field_confidence: dict = field(default_factory=dict)
    id: Optional[str] = None


@dataclass
class Issue:
    rule_id: str
    severity: str  # "error" | "warning" | "confirm"
    message: str
    evidence: dict = field(default_factory=dict)


# ---------- helpers ----------

def gstin_check_char(first14: str) -> str:
    """Compute the GSTIN check character (mod-36 algorithm)."""
    total = 0
    for i, ch in enumerate(first14):
        value = GSTIN_CHARSET.index(ch)
        product = value * (1 if i % 2 == 0 else 2)
        total += product // 36 + product % 36
    return GSTIN_CHARSET[(36 - total % 36) % 36]


def is_valid_gstin(gstin: str) -> bool:
    gstin = (gstin or "").strip().upper()
    if not GSTIN_PATTERN.match(gstin):
        return False
    return gstin_check_char(gstin[:14]) == gstin[14]


def normalise_invoice_no(invoice_no: str) -> str:
    """'SF/1123', 'sf-1123' and 'SF 1123' all become 'SF1123'."""
    return re.sub(r"[^A-Z0-9]", "", (invoice_no or "").upper())


def financial_year(d: date) -> str:
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


# ---------- rules V01 to V06, V09 (single invoice) ----------

REQUIRED_FIELDS = ["supplier_gstin", "invoice_no", "invoice_date", "taxable_value", "total"]


def check_required_fields(inv: Invoice) -> list[Issue]:  # V01
    missing = [f for f in REQUIRED_FIELDS if getattr(inv, f) in (None, "")]
    if missing:
        return [Issue("V01", "error", "Required fields are missing.", {"missing": missing})]
    return []


def check_gstin(inv: Invoice) -> list[Issue]:  # V02
    if inv.supplier_gstin and not is_valid_gstin(inv.supplier_gstin):
        return [Issue("V02", "error", "Supplier GSTIN format or check digit is invalid.",
                      {"gstin": inv.supplier_gstin})]
    return []


def check_arithmetic(inv: Invoice) -> list[Issue]:  # V05
    if inv.taxable_value is None or inv.total is None:
        return []
    expected = inv.taxable_value + inv.cgst + inv.sgst + inv.igst
    if abs(expected - inv.total) > ROUNDING_TOLERANCE:
        return [Issue("V05", "error", "Taxable value plus taxes does not equal the invoice total.",
                      {"expected_total": str(expected), "printed_total": str(inv.total)})]
    return []


def check_tax_type(inv: Invoice) -> list[Issue]:  # V06
    if not inv.supplier_gstin or not inv.place_of_supply:
        return []
    intra_state = inv.supplier_gstin[:2] == inv.place_of_supply
    has_split = inv.cgst > 0 or inv.sgst > 0
    has_igst = inv.igst > 0
    evidence = {"supplier_state": inv.supplier_gstin[:2], "place_of_supply": inv.place_of_supply}
    if intra_state and has_igst:
        return [Issue("V06", "error", "Intra-state supply normally carries CGST + SGST, not IGST.", evidence)]
    if not intra_state and has_split:
        return [Issue("V06", "error", "Inter-state supply normally carries IGST, not CGST + SGST.", evidence)]
    if intra_state and has_split and abs(inv.cgst - inv.sgst) > ROUNDING_TOLERANCE:
        return [Issue("V06", "error", "CGST and SGST should be equal.", evidence)]
    return []


def check_confidence(inv: Invoice, threshold: float = 0.80) -> list[Issue]:  # V09
    low = {f: c for f, c in inv.field_confidence.items() if f in REQUIRED_FIELDS and c < threshold}
    if low:
        return [Issue("V09", "confirm", "Please confirm these fields; the scan was unclear.", {"fields": low})]
    return []


# ---------- rules V03, V04 (across invoices) ----------

def check_duplicates(invoices: list[Invoice], similarity: int = 90, day_window: int = 3) -> list[Issue]:
    issues: list[Issue] = []
    seen: dict[tuple, Invoice] = {}
    for inv in invoices:
        if not (inv.supplier_gstin and inv.invoice_no and inv.invoice_date):
            continue
        key = (inv.supplier_gstin, normalise_invoice_no(inv.invoice_no), financial_year(inv.invoice_date))
        if key in seen:  # V03
            issues.append(Issue("V03", "error", "This invoice appears twice.",
                                {"invoice_ids": [seen[key].id, inv.id], "key": list(key)}))
            continue
        for other in seen.values():  # V04
            if (other.supplier_gstin == inv.supplier_gstin and other.total == inv.total
                    and abs((other.invoice_date - inv.invoice_date).days) <= day_window
                    and fuzz.ratio(normalise_invoice_no(other.invoice_no),
                                   normalise_invoice_no(inv.invoice_no)) >= similarity):
                issues.append(Issue("V04", "warning", "This may be a duplicate of another invoice.",
                                    {"invoice_ids": [other.id, inv.id]}))
                break
        seen[key] = inv
    return issues


# ---------- rule V08 (GSTR-2B) ----------

def check_gstr2b(inv: Invoice, gstr2b_rows: list[dict]) -> list[Issue]:
    """gstr2b_rows: dicts with supplier_gstin, invoice_no, total_tax (from the uploaded GSTR-2B)."""
    if not inv.supplier_gstin or not inv.invoice_no:
        return []
    key = (inv.supplier_gstin, normalise_invoice_no(inv.invoice_no))
    for row in gstr2b_rows:
        if (row["supplier_gstin"], normalise_invoice_no(row["invoice_no"])) == key:
            our_tax = inv.cgst + inv.sgst + inv.igst
            if abs(Decimal(str(row["total_tax"])) - our_tax) > ROUNDING_TOLERANCE:
                return [Issue("V08", "warning", "Tax amount differs from GSTR-2B.",
                              {"ours": str(our_tax), "gstr2b": str(row["total_tax"])})]
            return []
    return [Issue("V08", "warning", "Invoice not found in GSTR-2B; the supplier may not have filed it yet.",
                  {"key": list(key)})]


def validate_invoice(inv: Invoice) -> list[Issue]:
    issues: list[Issue] = []
    for rule in (check_required_fields, check_gstin, check_arithmetic, check_tax_type, check_confidence):
        issues.extend(rule(inv))
    return issues
