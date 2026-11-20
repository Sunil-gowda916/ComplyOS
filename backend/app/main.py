"""ComplyMate AI API (MVP skeleton).

Upload, extraction and the resolution agent are built in the prototype round
(23 Nov - 15 Dec). For now this exposes a health check and a validation
endpoint so the rule engine can be exercised from the frontend.
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from .validation import Invoice, validate_invoice

app = FastAPI(title="ComplyMate AI", version="0.1.0")


class InvoiceIn(BaseModel):
    supplier_gstin: Optional[str] = None
    invoice_no: Optional[str] = None
    invoice_date: Optional[date] = None
    place_of_supply: Optional[str] = None
    taxable_value: Optional[Decimal] = None
    cgst: Decimal = Decimal("0")
    sgst: Decimal = Decimal("0")
    igst: Decimal = Decimal("0")
    total: Optional[Decimal] = None
    field_confidence: dict = {}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/validate")
def validate(payload: InvoiceIn):
    issues = validate_invoice(Invoice(**payload.model_dump()))
    return {"issues": [i.__dict__ for i in issues]}
