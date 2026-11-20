from datetime import date
from decimal import Decimal as D

from app.validation import (
    Invoice, check_arithmetic, check_duplicates, check_gstr2b, check_tax_type,
    gstin_check_char, is_valid_gstin, normalise_invoice_no, validate_invoice,
)


def make_gstin(state: str, pan: str = "ABCDE1234F") -> str:
    first14 = f"{state}{pan}1Z"
    return first14 + gstin_check_char(first14)


KA = make_gstin("29")  # synthetic Karnataka supplier
TN = make_gstin("33")  # synthetic Tamil Nadu supplier


def inv(**kw) -> Invoice:
    base = dict(supplier_gstin=KA, invoice_no="INV-07", invoice_date=date(2026, 10, 5),
                place_of_supply="29", taxable_value=D("12000"), cgst=D("1080"), sgst=D("1080"),
                total=D("14160"))
    base.update(kw)
    return Invoice(**base)


def test_gstin_check_digit():
    assert is_valid_gstin(KA)
    assert not is_valid_gstin(KA[:-1] + ("0" if KA[-1] != "0" else "1"))
    assert not is_valid_gstin("29ABCDE1234F1Z")


def test_clean_invoice_passes():
    assert validate_invoice(inv()) == []


def test_missing_gstin():
    rules = [i.rule_id for i in validate_invoice(inv(supplier_gstin=None))]
    assert "V01" in rules


def test_arithmetic_mismatch():
    assert check_arithmetic(inv(total=D("14610")))[0].rule_id == "V05"


def test_interstate_with_cgst_sgst_is_flagged():
    assert check_tax_type(inv(supplier_gstin=TN))[0].rule_id == "V06"


def test_interstate_with_igst_passes():
    assert check_tax_type(inv(supplier_gstin=TN, cgst=D("0"), sgst=D("0"), igst=D("2160"))) == []


def test_normalise_invoice_no():
    assert normalise_invoice_no("SF/1123") == normalise_invoice_no("sf-1123") == "SF1123"


def test_exact_and_possible_duplicates():
    a = inv(id="a")
    b = inv(id="b")  # same bill uploaded twice
    c = inv(id="c", invoice_no="INV-071", invoice_date=date(2026, 10, 6))  # near-duplicate
    rules = [i.rule_id for i in check_duplicates([a, b, c])]
    assert rules == ["V03", "V04"]


def test_gstr2b_missing_and_match():
    rows = [{"supplier_gstin": KA, "invoice_no": "inv 07", "total_tax": "2160"}]
    assert check_gstr2b(inv(), rows) == []
    assert check_gstr2b(inv(invoice_no="INV-99"), rows)[0].rule_id == "V08"
