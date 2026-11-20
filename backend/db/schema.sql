-- ComplyMate AI MVP schema (PostgreSQL)
CREATE TABLE businesses (id UUID PRIMARY KEY, name TEXT, gstin CHAR(15), state_code CHAR(2), created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE users (id UUID PRIMARY KEY, business_id UUID REFERENCES businesses, role TEXT CHECK (role IN ('owner','accountant')), name TEXT, email TEXT UNIQUE, password_hash TEXT, language TEXT DEFAULT 'en');
CREATE TABLE suppliers (id UUID PRIMARY KEY, business_id UUID REFERENCES businesses, name TEXT, gstin CHAR(15), contact TEXT);
CREATE TABLE documents (id UUID PRIMARY KEY, business_id UUID REFERENCES businesses, file_path TEXT, file_hash TEXT, mime_type TEXT, uploaded_by UUID REFERENCES users, uploaded_at TIMESTAMPTZ DEFAULT now(), status TEXT);
CREATE TABLE invoices (id UUID PRIMARY KEY, document_id UUID REFERENCES documents, business_id UUID REFERENCES businesses, supplier_id UUID REFERENCES suppliers, invoice_no TEXT, invoice_no_norm TEXT, invoice_date DATE, fin_year TEXT, place_of_supply CHAR(2), taxable_value NUMERIC(14,2), cgst NUMERIC(14,2), sgst NUMERIC(14,2), igst NUMERIC(14,2), total NUMERIC(14,2), field_confidence JSONB, version INT DEFAULT 1);
CREATE TABLE gstr2b_entries (id UUID PRIMARY KEY, business_id UUID REFERENCES businesses, period TEXT, supplier_gstin CHAR(15), invoice_no_norm TEXT, invoice_date DATE, taxable_value NUMERIC(14,2), total_tax NUMERIC(14,2));
CREATE TABLE rules (id TEXT, version INT, description TEXT, params JSONB, source_ref TEXT, effective_from DATE, effective_to DATE, PRIMARY KEY (id, version));
CREATE TABLE exceptions (id UUID PRIMARY KEY, invoice_id UUID REFERENCES invoices, rule_id TEXT, rule_version INT, severity TEXT, evidence JSONB, status TEXT, owner_explanation TEXT, opened_at TIMESTAMPTZ DEFAULT now(), due_at TIMESTAMPTZ, closed_at TIMESTAMPTZ);
CREATE TABLE actions (id UUID PRIMARY KEY, exception_id UUID REFERENCES exceptions, type TEXT, draft_text TEXT, final_text TEXT, approved_by UUID REFERENCES users, approved_at TIMESTAMPTZ);
CREATE TABLE audit_log (id BIGSERIAL PRIMARY KEY, actor TEXT, entity TEXT, entity_id UUID, event TEXT, before JSONB, after JSONB, at TIMESTAMPTZ DEFAULT now());
CREATE UNIQUE INDEX uniq_invoice ON invoices (business_id, supplier_id, invoice_no_norm, fin_year);
