# ComplyOS

Agentic AI-powered compliance assistant for Indian MSMEs, simplifying invoice management, error detection and compliance issue resolution.

**Product: ComplyMate AI** — catches and resolves GST paperwork issues before filing day.
*Less Paperwork. Fewer Errors. Smarter Compliance.*

Tech4Bharat 2026 – GAVS Hackathon · Theme 3: MSME Finance & Compliance · Problem 3.1 · Agentic AI

> **Status:** early development. The deterministic validation engine (`backend/app/validation.py`) is implemented and unit-tested. Upload, extraction, the resolution agent and the dashboards are planned for the prototype round (23 Nov – 15 Dec 2026). Nothing here files real GST returns, and all data is synthetic.

## What it does

Small businesses usually discover paperwork problems at month-end: a duplicate bill, a missing supplier GSTIN, the wrong tax type, or an invoice missing from GSTR-2B. ComplyMate AI:

1. Reads uploaded invoice photos and PDFs into structured fields.
2. Runs **deterministic** checks (rules decide; the LLM never does tax maths).
3. Turns every failed check into a tracked exception.
4. Uses an **agent** to explain the issue, draft a fix or a supplier message, wait for the owner's approval, re-check the corrected document and escalate stalled issues to the accountant.
5. Gives the accountant organised records, an audit trail and an exportable report.

Filing always stays with the owner or their tax professional.

## Repository layout

```
docs/architecture.md    Architecture diagram, agent states, data model
backend/app/            FastAPI service + validation engine
backend/rules/          Versioned rule store (source + effective date per rule)
backend/db/schema.sql   PostgreSQL schema
backend/tests/          Unit tests for the validation rules
frontend/               React app (prototype round)
data/synthetic/         Synthetic invoices and GSTR-2B files (prototype round)
```

## Validation rules implemented so far

| ID | Check |
|---|---|
| V01 | Required fields present |
| V02 | GSTIN pattern and mod-36 check digit |
| V03 | Exact duplicate (supplier + normalised invoice number + financial year) |
| V04 | Possible duplicate (same supplier and total, ±3 days, ≥90% number similarity) |
| V05 | Taxable value + taxes = total (±₹1) |
| V06 | Intra-state → CGST + SGST; inter-state → IGST |
| V08 | Invoice present in GSTR-2B and tax amount matches |
| V09 | Low-confidence fields sent to the owner to confirm |

V07 (rate plausibility by invoice date) is defined in `backend/rules/rules.yaml`; its sources still need verifying.

## Run locally

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
uvicorn app.main:app --reload   # http://127.0.0.1:8000/docs
```

## Architecture

See [docs/architecture.md](docs/architecture.md).

## Boundaries

- No real GST filing; any filing step is simulated.
- Tax calculations and validation are deterministic Python, not LLM output.
- Rules carry an official source and effective date; the assistant says when it doesn't know.
- No message leaves the system without the owner's approval.
- Synthetic or anonymised data only. No WhatsApp, email, banking or GST-portal integration is claimed.
